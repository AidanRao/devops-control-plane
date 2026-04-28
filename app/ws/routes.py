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
)
from ..services.commands import update_result
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
    await manager.register(device_id, websocket)

    # 后续消息循环：处理 agent.tick 与 result.chunk 等事件。
    try:
        while True:
            data: Any = await websocket.receive_json()
            await _handle_incoming_event(device_id, data)
    except WebSocketDisconnect:
        manager.disconnect(device_id)


def _random_nonce() -> str:
    return secrets.token_hex(16)


async def _handle_incoming_event(device_id: str, data: Any) -> None:
    """根据事件类型进行最小处理。

    - agent.tick: 更新心跳状态
    - result.chunk: 解析结果并写入内存 commands 状态，然后回发 result.ack。
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
