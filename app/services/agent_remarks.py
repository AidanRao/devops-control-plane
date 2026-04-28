import json
import os
from typing import Dict, Optional

from ..config import settings


_cache: Optional[Dict[str, str]] = None


def _load() -> Dict[str, str]:
    global _cache
    if _cache is not None:
        return _cache

    path = settings.AGENT_REMARKS_PATH
    try:
        with open(path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        if isinstance(raw, dict):
            data: Dict[str, str] = {}
            for k, v in raw.items():
                if not isinstance(k, str) or not k:
                    continue
                if not isinstance(v, str):
                    continue
                vv = v.strip()
                if vv:
                    data[k] = vv
            _cache = data
            return data
    except FileNotFoundError:
        pass
    except Exception:
        # MVP: ignore broken file and start fresh.
        pass

    _cache = {}
    return _cache


def _persist(data: Dict[str, str]) -> None:
    path = settings.AGENT_REMARKS_PATH
    directory = os.path.dirname(path) or "."
    os.makedirs(directory, exist_ok=True)

    tmp_path = f"{path}.tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=True, indent=2, sort_keys=True)
        f.write("\n")
    os.replace(tmp_path, path)


def get_agent_remark(device_id: str) -> Optional[str]:
    if not device_id:
        return None
    return _load().get(device_id)


def set_agent_remark(device_id: str, remark: Optional[str]) -> Optional[str]:
    """Set remark (trimmed). Empty remark clears it and returns None."""

    if not device_id:
        return None

    value = (remark or "").strip()
    data = _load()
    if not value:
        if device_id in data:
            data.pop(device_id, None)
            _persist(data)
        return None

    if data.get(device_id) != value:
        data[device_id] = value
        _persist(data)
    return value

