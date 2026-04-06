from fastapi import APIRouter, HTTPException

from ..schemas.rest import (
    AgentsResponse,
    AgentInfo,
    CommandStatusResponse,
    CreateCommandRequest,
    CreateCommandResponse,
)
from ..services.commands import create_command, get_command_status
from ..ws.manager import manager
from ..schemas.ws import CommandPushPayload

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
    """返回当前在线 Agent 列表。"""

    agents = []
    for device_id in manager.active_connections.keys():
        agents.append(
            AgentInfo(
                device_id=device_id,
                hasDeviceToken=manager.has_valid_token(device_id),
                lastHeartbeat=manager.get_last_heartbeat(device_id),
            )
        )

    return AgentsResponse(agents=agents)
