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


def get_monitor_error_rate_threshold() -> float:
    """Tool error-rate cap for degraded status (OBS-B1-02 · override via env)."""
    raw = os.environ.get("MIMIR_MONITOR_ERROR_RATE_THRESHOLD", "").strip()
    if raw:
        try:
            value = float(raw)
            if 0.0 < value <= 1.0:
                return value
        except ValueError:
            pass
    return DEFAULT_ERROR_RATE_THRESHOLD


def get_monitor_window_seconds() -> float:
    """Sliding window for error rate and latency percentiles (seconds)."""
    raw = os.environ.get("MIMIR_MONITOR_WINDOW_SECONDS", "").strip()
    if raw:
        try:
            value = float(raw)
            if value > 0:
                return value
        except ValueError:
            pass
    return WINDOW_SECONDS

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


def get_agent_error_rate(
    window_seconds: Optional[float] = None,
) -> float:
    if window_seconds is None:
        window_seconds = get_monitor_window_seconds()
    """Error rate in [0, 1] over the sliding window."""
    cutoff = time.time() - window_seconds
    with _lock:
        window = [e for e in _recent if e["ts"] >= cutoff]
    if not window:
        return 0.0
    errors = sum(1 for e in window if not e["success"])
    return errors / len(window)


def get_agent_health_status(
    threshold: Optional[float] = None,
) -> str:
    if threshold is None:
        threshold = get_monitor_error_rate_threshold()
    rate = get_agent_error_rate()
    if rate > threshold:
        return "degraded"
    return "ok"


def _percentile(values: List[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = int(round((pct / 100.0) * (len(ordered) - 1)))
    idx = max(0, min(idx, len(ordered) - 1))
    return ordered[idx]


def get_tool_duration_percentiles(
    window_seconds: Optional[float] = None,
) -> Dict[str, float]:
    if window_seconds is None:
        window_seconds = get_monitor_window_seconds()
    """P50/P95/P99 tool call latency (ms) over the sliding window."""
    cutoff = time.time() - window_seconds
    with _lock:
        durs = [
            float(e["duration_ms"])
            for e in _recent
            if e["ts"] >= cutoff and float(e.get("duration_ms") or 0) > 0
        ]
    return {
        "p50_ms": _percentile(durs, 50),
        "p95_ms": _percentile(durs, 95),
        "p99_ms": _percentile(durs, 99),
    }


def snapshot_for_health() -> Dict[str, Any]:
    rate = get_agent_error_rate()
    pct = get_tool_duration_percentiles()
    return {
        "agent": get_agent_health_status(),
        "agent_error_rate": round(rate, 4),
        "agent_tool_p50_ms": round(pct["p50_ms"], 1),
        "agent_tool_p95_ms": round(pct["p95_ms"], 1),
        "agent_tool_p99_ms": round(pct["p99_ms"], 1),
    }


def _maybe_write_alert_locked() -> None:
    rate = get_agent_error_rate()
    threshold = get_monitor_error_rate_threshold()
    if rate <= threshold:
        return
    recent_errors = [e for e in list(_recent)[-20:] if not e["success"]]
    payload = {
        "timestamp": time.time(),
        "agent_error_rate": round(rate, 4),
        "threshold": threshold,
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
