import base64
import secrets
import time
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from nacl.exceptions import BadSignatureError
from nacl.signing import VerifyKey

from ..config import settings
from ..schemas.rest import CommandResultSummary
from ..schemas.ws import (
    ChallengePayload,
    ConnectParams,
    EventFrame,
    HeartbeatPayload,
    HelloAuth,
    HelloOkPayload,
    HelloPolicy,
    RequestFrame,
    ResponseFrame,
    ResultAckPayload,
    ResultChunkPayload,
    TerminalSessionAttachParams,
    TerminalSessionClosePayload,
    TerminalSessionClosedPayload,
    TerminalSessionErrorPayload,
    TerminalSessionOpenedPayload,
    TerminalSessionResizePayload,
    TerminalSessionSignalPayload,
    TerminalSessionStatePayload,
    TerminalStdinWritePayload,
    TerminalStdoutChunkPayload,
)
from ..services.commands import update_result
from ..services.agent_registry import agent_registry
from ..services.terminal_sessions import terminal_sessions
from .manager import manager


router = APIRouter()


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    """Gateway 风格 WS 接入点。

    流程：
    1. 接受连接；
    2. 发送 connect.challenge 事件（nonce + ts）；
    3. 接收客户端 connect 请求（req 帧 + ConnectParams）；
    4. 校验签名与时间窗，并核验 auth.token；
    5. 首次通过静态 Token 的设备签发 deviceToken，并在 hello-ok 中返回；
    6. 注册连接并进入事件循环，后续处理 agent.tick、result.chunk 等事件。
    """

    await websocket.accept()

    challenge = ChallengePayload(nonce=_random_nonce(), ts=int(time.time() * 1000))
    await websocket.send_json(
        {
            "type": "event",
            "event": "connect.challenge",
            "payload": challenge.model_dump(),
        }
    )

    try:
        raw = await websocket.receive_json()
    except WebSocketDisconnect:
        return

    try:
        req = RequestFrame.model_validate(raw)
    except Exception:
        await websocket.close(code=1002)
        return

    if req.method != "connect":
        await websocket.close(code=1002)
        return

    # ConnectParams 解析与校验。
    try:
        params = ConnectParams.model_validate(req.params)
    except Exception:
        await websocket.close(code=1002)
        return

    device_id = params.device.id

    # --- 签名与时间窗校验 ---

    # 校验 nonce 与 challenge 对齐。
    if params.device.nonce != challenge.nonce:
        await websocket.close(code=1008)
        return

    # 构造签名消息：deviceId|nonce|signedAt|role|token
    message = f"{device_id}|{challenge.nonce}|{params.device.signedAt}|{params.role}|{params.auth.token}".encode(
        "utf-8"
    )

    try:
        public_key_bytes = base64.b64decode(params.device.publicKey)
        signature_bytes = base64.b64decode(params.device.signature)
        verify_key = VerifyKey(public_key_bytes)
        verify_key.verify(message, signature_bytes)
    except (ValueError, BadSignatureError):
        # 公钥/签名格式错误或验签失败。
        await websocket.close(code=1008)
        return

    # 时间偏移限制，防止重放攻击。
    now_ms = int(time.time() * 1000)
    skew_ms = abs(now_ms - params.device.signedAt)
    if skew_ms > settings.MAX_SKEW_SECONDS * 1000:
        await websocket.close(code=1008)
        return

    # --- auth.token 校验与 deviceToken 发放/续期 ---

    auth_token = params.auth.token
    used_static = auth_token == settings.STATIC_GATEWAY_TOKEN
    token_ok = False
    used_device_token = False

    if used_static:
        token_ok = True
    else:
        if manager.validate_device_token(device_id, auth_token):
            token_ok = True
            used_device_token = True

    if not token_ok:
        # 未通过任一凭证校验，关闭连接。
        await websocket.close(code=1008)
        return

    device_token_to_issue: str | None = None

    if used_static and not manager.has_valid_token(device_id):
        # 首次使用静态 Token 且该设备无有效 token，签发新的 deviceToken。
        device_token_to_issue = secrets.token_urlsafe(32)
        manager.upsert_device_token(
            device_id, device_token_to_issue, settings.DEVICE_TOKEN_TTL_MINUTES
        )
    elif used_device_token:
        # 使用 deviceToken 连接时，刷新其 TTL。
        manager.upsert_device_token(device_id, auth_token, settings.DEVICE_TOKEN_TTL_MINUTES)

    hello_auth: HelloAuth | None = None
    if device_token_to_issue is not None:
        hello_auth = HelloAuth(
            deviceToken=device_token_to_issue,
            role=params.role,
            scopes=params.scopes,
        )

    hello_payload = HelloOkPayload(
        protocol=params.maxProtocol,
        policy=HelloPolicy(tickIntervalMs=settings.TICK_INTERVAL_MS),
        auth=hello_auth,
    )

    res = ResponseFrame(
        id=req.id,
        ok=True,
        payload=hello_payload.model_dump(),
    )

    await websocket.send_json(res.model_dump())

    # 握手完成，注册连接。
    agent_registry.ensure_agent(device_id)
    await manager.register(device_id, websocket)

    # 后续消息循环：处理 agent.tick 与 result.chunk 等事件。
    try:
        while True:
            data: Any = await websocket.receive_json()
            await _handle_incoming_event(device_id, data)
    except WebSocketDisconnect:
        manager.disconnect(device_id)


@router.websocket("/ws/terminal")
async def terminal_websocket_endpoint(websocket: WebSocket) -> None:
    await websocket.accept()

    try:
        while True:
            raw = await websocket.receive_json()
            await _handle_terminal_browser_message(websocket, raw)
    except WebSocketDisconnect:
        manager.detach_terminal_client(websocket)


def _random_nonce() -> str:
    return secrets.token_hex(16)


async def _handle_incoming_event(device_id: str, data: Any) -> None:
    """根据事件类型进行最小处理。

    - agent.tick: 更新心跳状态
    - result.chunk: 解析结果并写入内存 commands 状态，然后回发 result.ack。
    - terminal.*: 更新 terminal session 状态，并向浏览器附着端转发事件。
    """

    if not isinstance(data, dict):
        return

    if data.get("type") != "event":
        return

    event = data.get("event")
    payload = data.get("payload") or {}

    if event == "agent.tick":
        # 更新内存中的最后心跳时间，供 /api/agents 查询展示。
        try:
            hb = HeartbeatPayload.model_validate(payload)
            manager.update_heartbeat(device_id, hb.metrics)
        except Exception:
            manager.update_heartbeat(device_id)
        return

    if event == "result.chunk":
        try:
            chunk = ResultChunkPayload.model_validate(payload)
        except Exception:
            return

        # 基于分片是否 Final 构造单次汇总视图。
        status = "Running" if not chunk.isFinal else "Finished"
        result = CommandResultSummary(
            agent_id=chunk.agentId,
            status=status,
            exitCode=chunk.exitCode,
            stdout=chunk.stdoutChunk,
            stderr=chunk.stderrChunk,
        )

        # 更新任务状态机与内存结果。
        update_result(chunk.task_uuid, chunk.agentId, result)

        # 持久化成功后发送 result.ack，供 Agent 记录（MVP 不做重传窗口）。
        ack = ResultAckPayload(
            task_uuid=chunk.task_uuid,
            agentId=chunk.agentId,
            seq=chunk.seq,
            receivedAt=int(time.time() * 1000),
        )
        frame = EventFrame(event="result.ack", payload=ack.model_dump())
        await manager.send_json(device_id, frame.model_dump())
        return

    if event == "terminal.session.opened":
        try:
            payload_model = TerminalSessionOpenedPayload.model_validate(payload)
        except Exception:
            return
        session = terminal_sessions.mark_opened(
            session_id=payload_model.sessionId,
            agent_session_ref=payload_model.agentSessionRef,
            shell_pid=payload_model.shellPid,
            cwd=payload_model.cwd,
            title=payload_model.title,
        )
        await manager.broadcast_terminal_event(
            payload_model.sessionId,
            "terminal.session.state",
            {
                "sessionId": session.sessionId,
                "status": session.status,
                "title": session.title,
                "cwd": session.cwd or "",
                "cols": session.cols,
                "rows": session.rows,
                "seq": terminal_sessions.latest_seq(session.sessionId),
                "updatedAt": session.updatedAt,
            },
        )
        print('terminal.session.opened', payload_model)
        return

    if event == "terminal.stdout.chunk":
        try:
            payload_model = TerminalStdoutChunkPayload.model_validate(payload)
        except Exception:
            return
        chunk_payload = terminal_sessions.append_output_chunk(
            session_id=payload_model.sessionId,
            seq=payload_model.seq,
            stream=payload_model.stream,
            data=payload_model.data,
            cwd=payload_model.cwd or "",
            title=payload_model.title or "",
            is_binary=payload_model.isBinary,
        )
        await manager.broadcast_terminal_event(
            payload_model.sessionId,
            "terminal.stdout.chunk",
            chunk_payload,
        )
        return

    if event == "terminal.session.state":
        try:
            payload_model = TerminalSessionStatePayload.model_validate(payload)
        except Exception:
            return
        session = terminal_sessions.apply_state(
            session_id=payload_model.sessionId,
            status=payload_model.status,
            title=payload_model.title,
            cwd=payload_model.cwd or "",
            cols=payload_model.cols,
            rows=payload_model.rows,
            seq=payload_model.seq,
            updated_at=payload_model.updatedAt,
        )
        await manager.broadcast_terminal_event(
            payload_model.sessionId,
            "terminal.session.state",
            {
                "sessionId": session.sessionId,
                "status": session.status,
                "title": session.title,
                "cwd": session.cwd or "",
                "cols": session.cols,
                "rows": session.rows,
                "seq": payload_model.seq,
                "updatedAt": session.updatedAt,
            },
        )
        return

    if event == "terminal.session.closed":
        try:
            payload_model = TerminalSessionClosedPayload.model_validate(payload)
        except Exception:
            return
        session = terminal_sessions.mark_closed(
            payload_model.sessionId,
            exit_code=payload_model.exitCode,
            reason=payload_model.reason,
        )
        await manager.broadcast_terminal_event(
            payload_model.sessionId,
            "terminal.session.closed",
            {
                "sessionId": session.sessionId,
                "exitCode": session.exitCode,
                "reason": session.closeReason,
            },
        )
        return

    if event == "terminal.session.error":
        try:
            payload_model = TerminalSessionErrorPayload.model_validate(payload)
        except Exception:
            return
        session = terminal_sessions.mark_error(payload_model.sessionId, payload_model.message)
        await manager.broadcast_terminal_event(
            payload_model.sessionId,
            "terminal.session.error",
            {
                "sessionId": session.sessionId,
                "code": payload_model.code,
                "message": payload_model.message,
            },
        )


async def _handle_terminal_browser_message(websocket: WebSocket, raw: Any) -> None:
    try:
        req = RequestFrame.model_validate(raw)
    except Exception:
        await websocket.send_json(
            ResponseFrame(
                id=str(raw.get("id", "")) if isinstance(raw, dict) else "",
                ok=False,
                error={"code": "BAD_REQUEST", "message": "invalid terminal request"},
            ).model_dump()
        )
        return

    try:
        if req.method == "terminal.session.attach":
            params = TerminalSessionAttachParams.model_validate(req.params)
            session = terminal_sessions.get_session(params.sessionId)
            if session is None:
                await websocket.send_json(
                    ResponseFrame(
                        id=req.id,
                        ok=False,
                        error={"code": "SESSION_NOT_FOUND", "message": "session not found"},
                    ).model_dump()
                )
                return

            manager.attach_terminal_client(params.sessionId, websocket)
            replay = terminal_sessions.replay_after(params.sessionId, params.afterSeq)
            snapshot = terminal_sessions.get_snapshot(params.sessionId)
            if snapshot:
                snapshot.connectedClients = manager.count_terminal_clients(params.sessionId)

            await websocket.send_json(
                ResponseFrame(
                    id=req.id,
                    ok=True,
                    payload={
                        "sessionId": params.sessionId,
                        "status": session.status,
                        "seq": snapshot.seq if snapshot else 0,
                        "replayFrom": params.afterSeq + 1,
                    },
                ).model_dump()
            )
            if snapshot is not None:
                await websocket.send_json(
                    EventFrame(
                        event="terminal.session.state",
                        payload={
                            "sessionId": session.sessionId,
                            "status": session.status,
                            "title": session.title,
                            "cwd": session.cwd or "",
                            "cols": session.cols,
                            "rows": session.rows,
                            "seq": snapshot.seq,
                            "updatedAt": session.updatedAt,
                        },
                    ).model_dump()
                )
            for item in replay:
                await websocket.send_json(
                    EventFrame(event="terminal.stdout.chunk", payload=item).model_dump()
                )
            return

        if req.method == "terminal.stdin.write":
            params = TerminalStdinWritePayload.model_validate(req.params)
            await _forward_terminal_event(params.sessionId, "terminal.stdin.write", params.model_dump())
            await websocket.send_json(
                ResponseFrame(id=req.id, ok=True, payload={"accepted": True}).model_dump()
            )
            return

        if req.method == "terminal.session.resize":
            params = TerminalSessionResizePayload.model_validate(req.params)
            await _forward_terminal_event(
                params.sessionId, "terminal.session.resize", params.model_dump()
            )
            await websocket.send_json(
                ResponseFrame(id=req.id, ok=True, payload={"accepted": True}).model_dump()
            )
            return

        if req.method == "terminal.session.signal":
            params = TerminalSessionSignalPayload.model_validate(req.params)
            await _forward_terminal_event(
                params.sessionId, "terminal.session.signal", params.model_dump()
            )
            await websocket.send_json(
                ResponseFrame(id=req.id, ok=True, payload={"accepted": True}).model_dump()
            )
            return

        if req.method == "terminal.session.close":
            params = TerminalSessionClosePayload.model_validate(req.params)
            terminal_sessions.mark_closing(params.sessionId, params.reason)
            await _forward_terminal_event(
                params.sessionId, "terminal.session.close", params.model_dump()
            )
            await websocket.send_json(
                ResponseFrame(id=req.id, ok=True, payload={"accepted": True}).model_dump()
            )
            return
    except KeyError:
        await websocket.send_json(
            ResponseFrame(
                id=req.id,
                ok=False,
                error={"code": "SESSION_NOT_FOUND", "message": "session not found"},
            ).model_dump()
        )
        return
    except ValueError as exc:
        await websocket.send_json(
            ResponseFrame(
                id=req.id,
                ok=False,
                error={"code": "BAD_REQUEST", "message": str(exc)},
            ).model_dump()
        )
        return

    await websocket.send_json(
        ResponseFrame(
            id=req.id,
            ok=False,
            error={"code": "METHOD_NOT_SUPPORTED", "message": f"unsupported method: {req.method}"},
        ).model_dump()
    )


async def _forward_terminal_event(session_id: str, event: str, payload: dict) -> None:
    session = terminal_sessions.get_session(session_id)
    if session is None:
        raise KeyError(session_id)
    if not manager.has_connection(session.deviceId):
        raise ValueError("agent is offline")
    await manager.send_event(session.deviceId, event, payload)
