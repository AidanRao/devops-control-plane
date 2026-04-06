from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, Optional

from fastapi import WebSocket

from ..schemas.ws import CommandPushPayload


@dataclass
class DeviceTokenInfo:
    token: str
    expires_at: datetime


@dataclass
class DeviceMeta:
    """连接的运行时元信息，例如心跳时间。"""

    last_heartbeat: Optional[datetime] = None


class ConnectionManager:
    """最小连接管理器：维护 device_id + WebSocket 与 deviceToken 映射。

    TODO:
    - 增加连接元数据（最后心跳时间、角色、scope 等）。
    - 增加并发访问保护（MVP 假定单进程事件循环即可）。
    """

    def __init__(self) -> None:
        self.active_connections: Dict[str, WebSocket] = {}
        # 每个设备一个 deviceToken 记录，仅存于内存。
        self.tokens: Dict[str, DeviceTokenInfo] = {}
        # 设备运行时元信息，例如最后一次心跳时间。
        self.meta: Dict[str, DeviceMeta] = {}

    async def register(self, device_id: str, websocket: WebSocket) -> None:
        self.active_connections[device_id] = websocket

    def disconnect(self, device_id: str) -> None:
        self.active_connections.pop(device_id, None)

    async def send_json(self, device_id: str, message: dict) -> None:
        ws = self.active_connections.get(device_id)
        if ws is not None:
            await ws.send_json(message)

    async def broadcast_command(self, payload: CommandPushPayload) -> None:
        """向所有在线 Agent 广播 command.push。MVP 不做目标筛选。"""

        message = {
            "type": "event",
            "event": "command.push",
            "payload": payload.model_dump(),
        }
        for ws in list(self.active_connections.values()):
            await ws.send_json(message)

    # ---- deviceToken 管理 ----

    def upsert_device_token(self, device_id: str, token: str, ttl_minutes: int) -> None:
        """为设备记录/刷新 deviceToken 及过期时间。"""

        self.tokens[device_id] = DeviceTokenInfo(
            token=token,
            expires_at=datetime.utcnow() + timedelta(minutes=ttl_minutes),
        )

    def _get_token_info(self, device_id: str) -> Optional[DeviceTokenInfo]:
        info = self.tokens.get(device_id)
        if not info:
            return None
        if info.expires_at < datetime.utcnow():
            # 过期即清理。
            self.tokens.pop(device_id, None)
            return None
        return info

    def has_valid_token(self, device_id: str) -> bool:
        return self._get_token_info(device_id) is not None

    def validate_device_token(self, device_id: str, token: str) -> bool:
        info = self._get_token_info(device_id)
        if not info:
            return False
        return info.token == token

    # ---- 心跳与在线信息 ----

    def update_heartbeat(self, device_id: str) -> None:
        """记录设备最近一次心跳时间。"""

        meta = self.meta.get(device_id)
        if meta is None:
            meta = DeviceMeta()
            self.meta[device_id] = meta
        meta.last_heartbeat = datetime.utcnow()

    def get_last_heartbeat(self, device_id: str) -> Optional[datetime]:
        meta = self.meta.get(device_id)
        return meta.last_heartbeat if meta else None


manager = ConnectionManager()
