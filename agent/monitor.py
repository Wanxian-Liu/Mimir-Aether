"""E-006 D6-0b — agent tool error-rate monitoring and health snapshot."""

from __future__ import annotations

import json
import os
import threading
import time
from collections import deque
from pathlib import Path
from typing import Any, Deque, Dict, List, Optional

DEFAULT_ERROR_RATE_THRESHOLD = 0.10
CHECK_EVERY_N_CALLS = 10
WINDOW_SECONDS = 300.0

_lock = threading.RLock()
_recent: Deque[Dict[str, Any]] = deque(maxlen=1000)
_total_calls = 0
_alerts_path: Optional[Path] = None


def _alerts_file() -> Path:
    global _alerts_path
    if _alerts_path is None:
        from mimir_constants import get_mimir_home

        path = Path(get_mimir_home()) / "data" / "monitor_alerts.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        _alerts_path = path
    return _alerts_path


def record_tool_outcome(
    tool_name: str,
    *,
    success: bool,
    duration_ms: float = 0.0,
    error_message: str = "",
    session_id: str = "",
) -> None:
    """Track one tool call outcome; may emit monitor_alerts.json."""
    global _total_calls
    entry = {
        "ts": time.time(),
        "tool_name": tool_name,
        "success": success,
        "duration_ms": duration_ms,
        "error_message": error_message or "",
        "session_id": session_id,
    }
    with _lock:
        _recent.append(entry)
        _total_calls += 1
        if _total_calls % CHECK_EVERY_N_CALLS == 0:
            _maybe_write_alert_locked()


def get_agent_error_rate(window_seconds: float = WINDOW_SECONDS) -> float:
    """Error rate in [0, 1] over the sliding window."""
    cutoff = time.time() - window_seconds
    with _lock:
        window = [e for e in _recent if e["ts"] >= cutoff]
    if not window:
        return 0.0
    errors = sum(1 for e in window if not e["success"])
    return errors / len(window)


def get_agent_health_status(threshold: float = DEFAULT_ERROR_RATE_THRESHOLD) -> str:
    rate = get_agent_error_rate()
    if rate > threshold:
        return "degraded"
    return "ok"


def snapshot_for_health() -> Dict[str, Any]:
    rate = get_agent_error_rate()
    return {
        "agent": get_agent_health_status(),
        "agent_error_rate": round(rate, 4),
    }


def _maybe_write_alert_locked() -> None:
    rate = get_agent_error_rate()
    if rate <= DEFAULT_ERROR_RATE_THRESHOLD:
        return
    recent_errors = [e for e in list(_recent)[-20:] if not e["success"]]
    payload = {
        "timestamp": time.time(),
        "agent_error_rate": round(rate, 4),
        "threshold": DEFAULT_ERROR_RATE_THRESHOLD,
        "recent_errors": recent_errors,
    }
    path = _alerts_file()
    try:
        existing: List[Dict[str, Any]] = []
        if path.exists():
            existing = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(existing, list):
                existing = [existing]
        existing.append(payload)
        path.write_text(json.dumps(existing[-50:], ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError:
        pass


def reset_monitor_state() -> None:
    """Test helper."""
    global _total_calls, _alerts_path
    with _lock:
        _recent.clear()
        _total_calls = 0
        _alerts_path = None
