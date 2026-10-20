"""Lightweight flight-recorder ("black box") diagnostic logger and offline simulator.

Writes millisecond-stamped trace events to /config/oukitel_diag.log via a dedicated
background daemon thread so it never performs blocking disk I/O on Home Assistant's
event loop. Also supports /config/oukitel_simulate_offline.flag to simulate a router
fiber cut for the Oukitel Cloud API without disconnecting the home network.
"""

from __future__ import annotations

from datetime import datetime
import json
import os
import queue
import threading
from typing import Any

_DIAG_PATHS = ("/config/oukitel_diag.log", r"R:\oukitel_diag.log")
_OFFLINE_FLAG_PATHS = (
    "/config/oukitel_simulate_offline.flag",
    r"R:\oukitel_simulate_offline.flag",
)
_MAX_LOG_BYTES = 2 * 1024 * 1024  # 2 MB cap

_LOG_QUEUE: queue.SimpleQueue[str] = queue.SimpleQueue()
_WRITER_STARTED = False
_WRITER_LOCK = threading.Lock()
_CACHED_DIAG_PATH: str | None = None


def _resolve_diag_path() -> str:
    global _CACHED_DIAG_PATH
    if _CACHED_DIAG_PATH is not None:
        return _CACHED_DIAG_PATH
    if os.path.isdir("/config"):
        _CACHED_DIAG_PATH = "/config/oukitel_diag.log"
    elif os.path.isdir("R:\\"):
        _CACHED_DIAG_PATH = r"R:\oukitel_diag.log"
    else:
        _CACHED_DIAG_PATH = os.path.join(os.path.dirname(__file__), "oukitel_diag.log")
    return _CACHED_DIAG_PATH


def _writer_loop() -> None:
    """Background daemon thread that flushes queued diagnostic lines to disk."""
    while True:
        try:
            line = _LOG_QUEUE.get()
            if not line:
                continue
            batch = [line]
            while not _LOG_QUEUE.empty() and len(batch) < 100:
                try:
                    batch.append(_LOG_QUEUE.get_nowait())
                except Exception:
                    break

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

            with open(path, "a", encoding="utf-8") as f:
                f.writelines(batch)
        except Exception:
            pass


def _ensure_writer() -> None:
    global _WRITER_STARTED
    if _WRITER_STARTED:
        return
    with _WRITER_LOCK:
        if not _WRITER_STARTED:
            t = threading.Thread(target=_writer_loop, name="oukitel_diag_writer", daemon=True)
            t.start()
            _WRITER_STARTED = True


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
    """Enqueue a structured diagnostic line (100% non-blocking on the event loop)."""
    try:
        _ensure_writer()
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        clean_details = {k: _serialize_val(v) for k, v in details.items()}
        line = f"[{ts}] [{event}] {json.dumps(clean_details, ensure_ascii=False)}\n"
        _LOG_QUEUE.put_nowait(line)
    except Exception:
        pass
