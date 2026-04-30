from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
from datetime import datetime, timezone
from typing import Dict, List, Optional
from uuid import uuid4

from ..schemas.rest import TerminalSession, TerminalSessionSnapshot


MAX_REPLAY_CHUNKS = 1000


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class TerminalSessionStore:
    def __init__(self) -> None:
        self._sessions: Dict[str, TerminalSession] = {}
        self._device_index: Dict[str, List[str]] = defaultdict(list)
        self._replay_buffers: Dict[str, List[dict]] = defaultdict(list)
        self._agent_session_refs: Dict[str, str] = {}
        self._session_pids: Dict[str, int] = {}

    def reset(self) -> None:
        self._sessions.clear()
        self._device_index.clear()
        self._replay_buffers.clear()
        self._agent_session_refs.clear()
        self._session_pids.clear()

    def create_session(
        self,
        *,
        device_id: str,
        shell: str,
        cwd: str,
        env: Optional[dict[str, str]],
        cols: int,
        rows: int,
        title: str,
    ) -> TerminalSession:
        now = _now_iso()
        session = TerminalSession(
            sessionId=f"ts_{uuid4().hex}",
            deviceId=device_id,
            status="opening",
            title=title or shell.rsplit("/", 1)[-1],
            shell=shell,
            cwd=cwd or None,
            envSummary=deepcopy(env) if env else None,
            cols=cols,
            rows=rows,
            createdAt=now,
            updatedAt=now,
            lastActiveAt=now,
            exitCode=None,
            closeReason=None,
        )
        self._sessions[session.sessionId] = session
        self._device_index[device_id].append(session.sessionId)
        return session

    def list_sessions_for_device(self, device_id: str) -> List[TerminalSession]:
        ids = self._device_index.get(device_id, [])
        sessions = [self._sessions[sid] for sid in ids if sid in self._sessions]
        return [session for session in sessions if session.status != "closed"]

    def get_session(self, session_id: str) -> Optional[TerminalSession]:
        return self._sessions.get(session_id)

    def get_snapshot(self, session_id: str) -> Optional[TerminalSessionSnapshot]:
        session = self._sessions.get(session_id)
        if session is None:
            return None
        return TerminalSessionSnapshot(
            session=session,
            capabilities={
                "resize": True,
                "signal": True,
                "reconnect": True,
                "binaryChunk": False,
            },
            seq=self.latest_seq(session_id),
            connectedClients=0,
        )

    def latest_seq(self, session_id: str) -> int:
        buffer = self._replay_buffers.get(session_id, [])
        if not buffer:
            return 0
        return int(buffer[-1]["seq"])

    def update_session_title(self, session_id: str, title: str) -> TerminalSession:
        session = self._require(session_id)
        session.title = title or session.title
        session.updatedAt = _now_iso()
        return session

    def mark_opening(self, session_id: str) -> TerminalSession:
        session = self._require(session_id)
        session.status = "opening"
        session.updatedAt = _now_iso()
        return session

    def mark_closing(self, session_id: str, reason: Optional[str] = None) -> TerminalSession:
        session = self._require(session_id)
        session.status = "closing"
        session.closeReason = reason
        session.updatedAt = _now_iso()
        return session

    def mark_opened(
        self,
        *,
        session_id: str,
        agent_session_ref: str,
        shell_pid: int,
        cwd: str,
        title: str,
    ) -> TerminalSession:
        session = self._require(session_id)
        session.status = "open"
        session.cwd = cwd or session.cwd
        session.title = title or session.title
        session.updatedAt = _now_iso()
        session.lastActiveAt = session.updatedAt
        self._agent_session_refs[session_id] = agent_session_ref
        self._session_pids[session_id] = shell_pid
        return session

    def append_output_chunk(
        self,
        *,
        session_id: str,
        seq: int,
        stream: str,
        data: str,
        cwd: str,
        title: str,
        is_binary: bool,
    ) -> dict:
        session = self._require(session_id)
        payload = {
            "sessionId": session_id,
            "seq": int(seq),
            "stream": stream,
            "data": data,
            "cwd": cwd or session.cwd or "",
            "title": title or session.title,
            "isBinary": bool(is_binary),
        }
        buffer = self._replay_buffers[session_id]
        buffer.append(payload)
        if len(buffer) > MAX_REPLAY_CHUNKS:
            del buffer[: len(buffer) - MAX_REPLAY_CHUNKS]

        session.cwd = payload["cwd"] or session.cwd
        session.title = payload["title"] or session.title
        session.updatedAt = _now_iso()
        session.lastActiveAt = session.updatedAt
        return payload

    def apply_state(
        self,
        *,
        session_id: str,
        status: str,
        title: str,
        cwd: str,
        cols: int,
        rows: int,
        seq: int,
        updated_at: Optional[str],
    ) -> TerminalSession:
        session = self._require(session_id)
        session.status = status
        session.title = title or session.title
        session.cwd = cwd or session.cwd
        session.cols = cols
        session.rows = rows
        session.updatedAt = updated_at or _now_iso()
        session.lastActiveAt = session.updatedAt
        if seq > self.latest_seq(session_id):
            # Keep cursor aligned even if no chunk is emitted.
            self._replay_buffers.setdefault(session_id, [])
        return session

    def mark_closed(self, session_id: str, exit_code: Optional[int], reason: str) -> TerminalSession:
        session = self._require(session_id)
        session.status = "closed"
        session.exitCode = exit_code
        session.closeReason = reason
        session.updatedAt = _now_iso()
        session.lastActiveAt = session.updatedAt
        return session

    def mark_error(self, session_id: str, message: str) -> TerminalSession:
        session = self._require(session_id)
        session.status = "error"
        session.closeReason = message
        session.updatedAt = _now_iso()
        session.lastActiveAt = session.updatedAt
        return session

    def replay_after(self, session_id: str, after_seq: int) -> List[dict]:
        buffer = self._replay_buffers.get(session_id, [])
        return [deepcopy(item) for item in buffer if int(item["seq"]) > int(after_seq)]

    def _require(self, session_id: str) -> TerminalSession:
        session = self._sessions.get(session_id)
        if session is None:
            raise KeyError(session_id)
        return session


terminal_sessions = TerminalSessionStore()
