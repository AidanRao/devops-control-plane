from fastapi import APIRouter, HTTPException

from ..schemas.rest import (
    AgentCommandHistoryResponse,
    AgentsResponse,
    AgentInfo,
    CommandStatusResponse,
    CreateTerminalSessionRequest,
    CreateTerminalSessionResponse,
    CreateCommandRequest,
    CreateCommandResponse,
    DeleteTerminalSessionResponse,
    ListTerminalSessionsResponse,
    TerminalSessionSnapshot,
    UpdateAgentRemarkRequest,
    UpdateAgentRemarkResponse,
    UpdateTerminalSessionRequest,
)
from ..services.commands import (
    create_command,
    get_command_status,
    list_commands_for_agent,
)
from ..services.agent_registry import agent_registry
from ..services.terminal_sessions import terminal_sessions
from ..ws.manager import manager
from ..schemas.ws import CommandPushPayload, TerminalSessionClosePayload, TerminalSessionOpenPayload

import uuid


router = APIRouter()


@router.post("/commands", response_model=CreateCommandResponse)
async def create_command_endpoint(body: CreateCommandRequest) -> CreateCommandResponse:
    """创建命令任务并通过 WS 向 Agent 广播 command.push。

    MVP 中不区分目标 Agent，仅做简单广播。
    """

    task_uuid = create_command(body)

    payload = CommandPushPayload(
        task_uuid=task_uuid,
        command=body.command,
        correlationId=str(uuid.uuid4()),
        timeoutSeconds=body.timeoutSeconds,
        workDir=body.workDir,
    )

    # 广播给所有在线 Agent。
    await manager.broadcast_command(payload)

    return CreateCommandResponse(task_uuid=task_uuid)


@router.get("/commands/{task_uuid}", response_model=CommandStatusResponse)
async def get_command_status_endpoint(task_uuid: str) -> CommandStatusResponse:
    """按 task_uuid 查询命令状态与结果。"""

    status = get_command_status(task_uuid)
    if status is None:
        raise HTTPException(status_code=404, detail="command not found")
    return status


@router.get("/agents", response_model=AgentsResponse)
async def list_agents() -> AgentsResponse:
    """返回在线 + 已持久化离线 Agent 列表。"""

    agents = []
    persisted = {record.device_id: record for record in agent_registry.list_agents()}
    all_device_ids = set(persisted.keys()) | set(manager.active_connections.keys())

    for device_id in sorted(all_device_ids):
        metrics = manager.get_last_metrics(device_id)
        record = persisted.get(device_id)
        agents.append(
            AgentInfo(
                device_id=device_id,
                online=device_id in manager.active_connections,
                hasDeviceToken=manager.has_valid_token(device_id),
                lastHeartbeat=manager.get_last_heartbeat(device_id),
                cpuPercent=metrics.cpuPercent if metrics else None,
                memPercent=metrics.memPercent if metrics else None,
                memUsed=metrics.memUsed if metrics else None,
                memTotal=metrics.memTotal if metrics else None,
                remark=record.remark if record else None,
            )
        )

    return AgentsResponse(agents=agents)


@router.put("/agents/{device_id}/remark", response_model=UpdateAgentRemarkResponse)
async def update_agent_remark(
    device_id: str, body: UpdateAgentRemarkRequest
) -> UpdateAgentRemarkResponse:
    """更新某个 Agent 的备注（持久化到 agent registry）。"""

    saved = agent_registry.set_remark(device_id, body.remark)
    return UpdateAgentRemarkResponse(device_id=device_id, remark=saved)



@router.get(
    "/agents/{device_id}/commands",
    response_model=AgentCommandHistoryResponse,
)
async def list_agent_commands(device_id: str) -> AgentCommandHistoryResponse:
    """返回某个 Agent 参与过的历史命令，按时间倒序。"""

    items = list_commands_for_agent(device_id)
    return AgentCommandHistoryResponse(device_id=device_id, items=items)


@router.post(
    "/agents/{device_id}/terminal-sessions",
    response_model=CreateTerminalSessionResponse,
)
async def create_terminal_session(
    device_id: str, body: CreateTerminalSessionRequest
) -> CreateTerminalSessionResponse:
    if not manager.has_connection(device_id):
        raise HTTPException(status_code=503, detail="agent is offline")

    session = terminal_sessions.create_session(
        device_id=device_id,
        shell=body.shell,
        cwd=body.cwd,
        env=body.env,
        cols=body.cols,
        rows=body.rows,
        title=body.title or body.shell.rsplit("/", 1)[-1],
    )

    payload = TerminalSessionOpenPayload(
        requestId=str(uuid.uuid4()),
        sessionId=session.sessionId,
        deviceId=device_id,
        shell=body.shell,
        cwd=body.cwd,
        env=body.env,
        cols=body.cols,
        rows=body.rows,
        title=session.title,
    )
    await manager.send_event(device_id, "terminal.session.open", payload.model_dump())
    return CreateTerminalSessionResponse(session=session)


@router.get(
    "/agents/{device_id}/terminal-sessions",
    response_model=ListTerminalSessionsResponse,
)
async def list_terminal_sessions(device_id: str) -> ListTerminalSessionsResponse:
    return ListTerminalSessionsResponse(items=terminal_sessions.list_sessions_for_device(device_id))


@router.get(
    "/agents/{device_id}/terminal-sessions/{session_id}",
    response_model=TerminalSessionSnapshot,
)
async def get_terminal_session(
    device_id: str, session_id: str
) -> TerminalSessionSnapshot:
    snapshot = terminal_sessions.get_snapshot(session_id)
    if snapshot is None or snapshot.session.deviceId != device_id:
        raise HTTPException(status_code=404, detail="terminal session not found")
    snapshot.connectedClients = manager.count_terminal_clients(session_id)
    return snapshot


@router.patch(
    "/agents/{device_id}/terminal-sessions/{session_id}",
    response_model=CreateTerminalSessionResponse,
)
async def update_terminal_session(
    device_id: str, session_id: str, body: UpdateTerminalSessionRequest
) -> CreateTerminalSessionResponse:
    session = terminal_sessions.get_session(session_id)
    if session is None or session.deviceId != device_id:
        raise HTTPException(status_code=404, detail="terminal session not found")
    updated = terminal_sessions.update_session_title(session_id, body.title)
    return CreateTerminalSessionResponse(session=updated)


@router.delete(
    "/agents/{device_id}/terminal-sessions/{session_id}",
    response_model=DeleteTerminalSessionResponse,
)
async def delete_terminal_session(
    device_id: str, session_id: str
) -> DeleteTerminalSessionResponse:
    session = terminal_sessions.get_session(session_id)
    if session is None or session.deviceId != device_id:
        raise HTTPException(status_code=404, detail="terminal session not found")

    if manager.has_connection(device_id):
        terminal_sessions.mark_closing(session_id, "client_closed")
        payload = TerminalSessionClosePayload(sessionId=session_id, reason="client_closed")
        await manager.send_event(device_id, "terminal.session.close", payload.model_dump())
    else:
        terminal_sessions.mark_closed(session_id, exit_code=None, reason="agent_offline")

    return DeleteTerminalSessionResponse(ok=True)
