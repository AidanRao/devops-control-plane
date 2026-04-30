from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional

from fastapi import WebSocket

from ..schemas.ws import CommandPushPayload, MetricsSnapshot
from ..services.agent_registry import agent_registry


@dataclass
class DeviceTokenInfo:
    token: str
    expires_at: datetime


@dataclass
class DeviceMeta:
    """连接的运行时元信息，例如心跳时间。"""

    last_heartbeat: Optional[datetime] = None
    last_metrics: Optional[MetricsSnapshot] = None


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
        # browser terminal ws 按 session 维度附着。
        self.terminal_clients: Dict[str, Dict[int, WebSocket]] = {}
        self.terminal_client_session: Dict[int, str] = {}

    async def register(self, device_id: str, websocket: WebSocket) -> None:
        self.active_connections[device_id] = websocket

    def disconnect(self, device_id: str) -> None:
        self.active_connections.pop(device_id, None)

    async def send_json(self, device_id: str, message: dict) -> None:
        ws = self.active_connections.get(device_id)
        if ws is not None:
            await ws.send_json(message)

    async def send_event(self, device_id: str, event: str, payload: dict) -> None:
        await self.send_json(
            device_id,
            {
                "type": "event",
                "event": event,
                "payload": payload,
            },
        )

    def has_connection(self, device_id: str) -> bool:
        return device_id in self.active_connections

    async def broadcast_command(self, payload: CommandPushPayload) -> None:
        """向所有在线 Agent 广播 command.push。MVP 不做目标筛选。"""

        message = {
            "type": "event",
            "event": "command.push",
            "payload": payload.model_dump(),
        }
        for ws in list(self.active_connections.values()):
            await ws.send_json(message)

    def attach_terminal_client(self, session_id: str, websocket: WebSocket) -> None:
        ws_id = id(websocket)
        old_session_id = self.terminal_client_session.get(ws_id)
        if old_session_id and old_session_id != session_id:
            clients = self.terminal_clients.get(old_session_id, {})
            clients.pop(ws_id, None)
            if not clients:
                self.terminal_clients.pop(old_session_id, None)

        clients = self.terminal_clients.setdefault(session_id, {})
        clients[ws_id] = websocket
        self.terminal_client_session[ws_id] = session_id

    def detach_terminal_client(self, websocket: WebSocket) -> None:
        ws_id = id(websocket)
        session_id = self.terminal_client_session.pop(ws_id, None)
        if not session_id:
            return
        clients = self.terminal_clients.get(session_id, {})
        clients.pop(ws_id, None)
        if not clients:
            self.terminal_clients.pop(session_id, None)

    def count_terminal_clients(self, session_id: str) -> int:
        return len(self.terminal_clients.get(session_id, {}))

    async def broadcast_terminal_event(self, session_id: str, event: str, payload: dict) -> None:
        clients = list(self.terminal_clients.get(session_id, {}).values())
        stale: list[WebSocket] = []
        for ws in clients:
            try:
                await ws.send_json(
                    {
                        "type": "event",
                        "event": event,
                        "payload": payload,
                    }
                )
            except Exception:
                stale.append(ws)

        for ws in stale:
            self.detach_terminal_client(ws)

    # ---- deviceToken 管理 ----

    def upsert_device_token(self, device_id: str, token: str, ttl_minutes: int) -> None:
        """为设备记录/刷新 deviceToken 及过期时间。"""

        expires_at = datetime.now(timezone.utc) + timedelta(minutes=ttl_minutes)
        self.tokens[device_id] = DeviceTokenInfo(token=token, expires_at=expires_at)
        agent_registry.upsert_device_token(device_id, token, expires_at)

    def _get_token_info(self, device_id: str) -> Optional[DeviceTokenInfo]:
        info = self.tokens.get(device_id)
        if not info:
            record = agent_registry.get_agent(device_id)
            if record and record.device_token and record.token_expires_at:
                expires_at = record.token_expires_at
                if expires_at.tzinfo is None:
                    expires_at = expires_at.replace(tzinfo=timezone.utc)
                else:
                    expires_at = expires_at.astimezone(timezone.utc)
                if expires_at >= datetime.now(timezone.utc):
                    info = DeviceTokenInfo(
                        token=record.device_token,
                        expires_at=expires_at,
                    )
                    self.tokens[device_id] = info
                else:
                    return None
            else:
                return None
        if info.expires_at < datetime.now(timezone.utc):
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

    def update_heartbeat(self, device_id: str, metrics: Optional[MetricsSnapshot] = None) -> None:
        """记录设备最近一次心跳时间与资源快照。"""

        meta = self.meta.get(device_id)
        if meta is None:
            meta = DeviceMeta()
            self.meta[device_id] = meta
        meta.last_heartbeat = datetime.now(timezone.utc)
        if metrics is not None:
            meta.last_metrics = metrics

    def get_last_heartbeat(self, device_id: str) -> Optional[datetime]:
        meta = self.meta.get(device_id)
        return meta.last_heartbeat if meta else None

    def get_last_metrics(self, device_id: str) -> Optional[MetricsSnapshot]:
        meta = self.meta.get(device_id)
        return meta.last_metrics if meta else None


manager = ConnectionManager()
