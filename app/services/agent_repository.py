import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Protocol


@dataclass
class AgentRecord:
    device_id: str
    remark: Optional[str] = None
    device_token: Optional[str] = None
    token_expires_at: Optional[datetime] = None


class AgentRepository(Protocol):
    def list_agents(self) -> List[AgentRecord]:
        ...

    def get_agent(self, device_id: str) -> Optional[AgentRecord]:
        ...

    def save_agent(self, record: AgentRecord) -> AgentRecord:
        ...


def _to_utc_iso(dt: Optional[datetime]) -> Optional[str]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt.isoformat().replace("+00:00", "Z")


def _parse_utc_iso(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except Exception:
        return None


def _normalize_remark(value: Optional[str]) -> Optional[str]:
    vv = (value or "").strip()
    return vv or None


class JsonAgentRepository:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self._cache: Optional[Dict[str, AgentRecord]] = None

    def list_agents(self) -> List[AgentRecord]:
        return list(self._load().values())

    def get_agent(self, device_id: str) -> Optional[AgentRecord]:
        if not device_id:
            return None
        return self._load().get(device_id)

    def save_agent(self, record: AgentRecord) -> AgentRecord:
        data = self._load()
        data[record.device_id] = record
        self._persist(data)
        return record

    def _load(self) -> Dict[str, AgentRecord]:
        if self._cache is not None:
            return self._cache

        raw = self._read_registry_file()
        data: Dict[str, AgentRecord] = {}
        if isinstance(raw, dict):
            for device_id, payload in raw.items():
                if not isinstance(device_id, str) or not device_id:
                    continue
                if not isinstance(payload, dict):
                    continue
                record = AgentRecord(
                    device_id=payload.get("deviceId") or device_id,
                    remark=_normalize_remark(payload.get("remark")),
                    device_token=payload.get("deviceToken") or None,
                    token_expires_at=_parse_utc_iso(payload.get("tokenExpiresAt")),
                )
                data[device_id] = record

        self._cache = data
        return data

    def _read_registry_file(self) -> Optional[dict]:
        try:
            with self.path.open("r", encoding="utf-8") as f:
                raw = json.load(f)
            return raw if isinstance(raw, dict) else {}
        except FileNotFoundError:
            return None
        except Exception:
            # Broken file should not crash the app; start fresh.
            return {}

    def _persist(self, data: Dict[str, AgentRecord]) -> None:
        directory = self.path.parent
        os.makedirs(directory, exist_ok=True)

        payload = {
            device_id: {
                "deviceId": record.device_id,
                "remark": _normalize_remark(record.remark),
                "deviceToken": record.device_token,
                "tokenExpiresAt": _to_utc_iso(record.token_expires_at),
            }
            for device_id, record in sorted(data.items())
        }

        tmp_path = self.path.with_suffix(f"{self.path.suffix}.tmp")
        with tmp_path.open("w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=True, indent=2, sort_keys=True)
            f.write("\n")
        os.replace(tmp_path, self.path)
        self._cache = data
