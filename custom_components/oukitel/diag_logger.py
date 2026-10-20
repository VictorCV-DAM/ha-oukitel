"""Lightweight flight-recorder ("black box") diagnostic logger and offline simulator.

Writes millisecond-stamped trace events to /config/oukitel_diag.log so LAN/offline
handshakes, tag reads, and raw TTLV frames can be inspected without trial-and-error.
Also supports /config/oukitel_simulate_offline.flag to simulate a router fiber cut
for the Oukitel Cloud API without disconnecting the home network.
"""

from __future__ import annotations

from datetime import datetime
import json
import os
from typing import Any

_DIAG_PATHS = ("/config/oukitel_diag.log", r"R:\oukitel_diag.log")
_OFFLINE_FLAG_PATHS = (
    "/config/oukitel_simulate_offline.flag",
    r"R:\oukitel_simulate_offline.flag",
)
_MAX_LOG_BYTES = 2 * 1024 * 1024  # 2 MB cap


def _resolve_diag_path() -> str:
    if os.path.isdir("/config"):
        return "/config/oukitel_diag.log"
    if os.path.isdir("R:\\"):
        return r"R:\oukitel_diag.log"
    return os.path.join(os.path.dirname(__file__), "oukitel_diag.log")


def is_offline_simulated() -> bool:
    """Return True if the offline simulation flag file exists."""
    try:
        for p in _OFFLINE_FLAG_PATHS:
            if os.path.exists(p):
                return True
    except Exception:
        pass
    return False


def _serialize_val(val: Any) -> Any:
    if isinstance(val, (bytes, bytearray)):
        return val.hex()
    if isinstance(val, dict):
        return {str(k): _serialize_val(v) for k, v in val.items()}
    if isinstance(val, (list, tuple)):
        return [_serialize_val(x) for x in val]
    return val


def diag_log(event: str, **details: Any) -> None:
    """Append a structured diagnostic line to /config/oukitel_diag.log."""
    try:
        path = _resolve_diag_path()
        try:
            if os.path.exists(path) and os.path.getsize(path) > _MAX_LOG_BYTES:
                with open(path, "rb") as f:
                    f.seek(-(_MAX_LOG_BYTES // 2), os.SEEK_END)
                    tail = f.read()
                with open(path, "wb") as f:
                    f.write(b"--- LOG ROTATED ---\n" + tail)
        except Exception:
            pass

        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        clean_details = {k: _serialize_val(v) for k, v in details.items()}
        line = f"[{ts}] [{event}] {json.dumps(clean_details, ensure_ascii=False)}\n"
        with open(path, "a", encoding="utf-8") as f:
            f.write(line)
    except Exception:
        pass
