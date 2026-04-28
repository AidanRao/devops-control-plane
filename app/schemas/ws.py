from typing import Any, Dict, List, Optional

from pydantic import BaseModel


class ChallengePayload(BaseModel):
    nonce: str
    ts: int


class EventFrame(BaseModel):
    type: str = "event"
    event: str
    payload: Any


class ClientInfo(BaseModel):
    id: str
    version: str
    platform: str
    mode: str


class DeviceInfo(BaseModel):
    id: str
    publicKey: str
    signature: str
    signedAt: int
    nonce: str


class AuthInfo(BaseModel):
    token: str


class ConnectParams(BaseModel):
    minProtocol: int
    maxProtocol: int
    client: ClientInfo
    role: str
    scopes: List[str] = []
    device: DeviceInfo
    auth: AuthInfo


class RequestFrame(BaseModel):
    type: str = "req"
    id: str
    method: str
    params: Any
    idempotencyKey: Optional[str] = None


class HelloPolicy(BaseModel):
    tickIntervalMs: int


class HelloAuth(BaseModel):
    deviceToken: str
    role: str
    scopes: List[str] = []


class HelloOkPayload(BaseModel):
    type: str = "hello-ok"
    protocol: int
    policy: HelloPolicy
    auth: Optional[HelloAuth] = None


class ResponseFrame(BaseModel):
    type: str = "res"
    id: str
    ok: bool
    payload: Optional[Any] = None
    error: Optional[Dict[str, Any]] = None


class CommandPushPayload(BaseModel):
    task_uuid: str
    command: str
    correlationId: str
    timeoutSeconds: int = 30


class ResultChunkPayload(BaseModel):
    """Agent -> Server 的结果分片事件负载，对齐 Go 侧 ResultChunkPayload。"""

    task_uuid: str
    correlationId: str
    agentId: str
    seq: int
    stdoutChunk: Optional[str] = None
    stderrChunk: Optional[str] = None
    exitCode: Optional[int] = None
    isFinal: bool = False
    sentAt: Optional[int] = None  # Agent 发送时间（毫秒时间戳），MVP 可为空


class ResultAckPayload(BaseModel):
    """Server -> Agent 的结果分片确认事件负载。"""

    task_uuid: str
    agentId: str
    seq: int
    receivedAt: int


class MetricsSnapshot(BaseModel):
    """Agent 所在节点的资源快照，嵌入在心跳中上报。"""

    cpuPercent: float
    memPercent: float
    memUsed: int
    memTotal: int
    load1: float
    numGoroutine: int


class HeartbeatPayload(BaseModel):
    deviceId: str
    ts: int
    metrics: Optional[MetricsSnapshot] = None
