from datetime import datetime
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class CreateCommandRequest(BaseModel):
    targets: List[str] = Field(
        default_factory=list,
        description="目标 Agent ID 列表；为空时表示广播到所有在线 Agent。",
    )
    command: str = Field(..., description="要执行的命令文本，例如 'uname -a'。")
    timeoutSeconds: int = Field(30, description="命令最大执行时间（秒）。")
    idempotencyKey: Optional[str] = Field(
        default=None,
        description="幂等键，MVP 仅存储，不做完整幂等实现。",
    )


class CreateCommandResponse(BaseModel):
    task_uuid: str


class CommandResultSummary(BaseModel):
    agent_id: str
    status: str
    exitCode: Optional[int] = None
    stdout: Optional[str] = None
    stderr: Optional[str] = None


class CommandStatusResponse(BaseModel):
    task_uuid: str
    status: str
    results: List[CommandResultSummary] = Field(
        default_factory=list,
        description="按 agent 聚合的执行结果列表。",
    )


class AgentInfo(BaseModel):
    """在线 Agent 的最小视图。"""

    device_id: str = Field(..., description="设备 ID（device_id）。")
    hasDeviceToken: bool = Field(
        ..., description="当前内存中是否存在有效的 deviceToken。"
    )
    lastHeartbeat: Optional[datetime] = Field(
        default=None,
        description="最近一次接收到的心跳时间（UTC）。",
    )


class AgentsResponse(BaseModel):
    agents: List[AgentInfo] = Field(
        default_factory=list,
        description="当前在线 Agent 列表。",
    )
