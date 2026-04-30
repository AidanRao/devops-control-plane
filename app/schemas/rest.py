from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class CreateCommandRequest(BaseModel):
    targets: List[str] = Field(
        default_factory=list,
        description="目标 Agent ID 列表；为空时表示广播到所有在线 Agent。",
    )
    command: str = Field(..., description="要执行的命令文本，例如 'uname -a'。")
    workDir: Optional[str] = Field(
        default=None,
        description="本次命令执行的工作目录；为空时使用 Agent 侧默认（shell.workDir 或进程当前目录）。",
        max_length=1024,
    )
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


class AgentCommandHistoryItem(BaseModel):
    """单个 Agent 的历史命令条目（按 Agent 聚合视角）。"""

    task_uuid: str
    command: str
    status: str = Field(
        ..., description="该 Agent 上的执行状态：Dispatching / Running / Finished 等。"
    )
    exitCode: Optional[int] = None
    createdAt: datetime = Field(..., description="命令创建时间（UTC）。")
    stdout: Optional[str] = None
    stderr: Optional[str] = None


class AgentCommandHistoryResponse(BaseModel):
    device_id: str
    items: List[AgentCommandHistoryItem] = Field(default_factory=list)


class AgentInfo(BaseModel):
    """Agent 的最小视图（在线 + 已持久化离线）。"""

    device_id: str = Field(..., description="设备 ID（device_id）。")
    online: bool = Field(..., description="当前是否在线。")
    hasDeviceToken: bool = Field(
        ..., description="当前是否存在有效的 deviceToken（可来自持久化恢复）。"
    )
    lastHeartbeat: Optional[datetime] = Field(
        default=None,
        description="最近一次接收到的心跳时间（UTC）。",
    )
    cpuPercent: Optional[float] = Field(default=None, description="CPU 使用率百分比。")
    memPercent: Optional[float] = Field(default=None, description="内存使用率百分比。")
    memUsed: Optional[int] = Field(default=None, description="已用内存（bytes）。")
    memTotal: Optional[int] = Field(default=None, description="总内存（bytes）。")
    remark: Optional[str] = Field(default=None, description="Agent 备注。")


class AgentsResponse(BaseModel):
    agents: List[AgentInfo] = Field(
        default_factory=list,
        description="当前 Agent 列表（包含在线与已持久化离线设备）。",
    )


class UpdateAgentRemarkRequest(BaseModel):
    remark: str = Field(
        default="",
        max_length=100,
        description="Agent 备注（<=100 字）。空字符串表示清空。",
    )


class UpdateAgentRemarkResponse(BaseModel):
    device_id: str
    remark: Optional[str] = None
