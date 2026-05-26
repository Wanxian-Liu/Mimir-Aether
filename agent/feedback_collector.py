"""Structured feedback events (IQ-EVO Wave 4 · record-only, no threshold mutation)."""

from __future__ import annotations

import json
import os
import threading
import time
from collections import deque
from pathlib import Path
from typing import Any, Deque, Dict, List, Optional

from mimir_constants import get_mimir_home

_lock = threading.Lock()
_recent: Deque[Dict[str, Any]] = deque(maxlen=200)


def feedback_collector_enabled() -> bool:
    return os.environ.get("MIMIR_FEEDBACK_COLLECTOR", "").strip().lower() in (
        "1",
        "true",
        "yes",
    )


def _events_path() -> Path:
    path = Path(get_mimir_home()) / "data" / "feedback_events.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def record_feedback_event(
    event_type: str,
    payload: Dict[str, Any],
    *,
    session_id: str = "",
) -> None:
    """Append one feedback event when ``MIMIR_FEEDBACK_COLLECTOR=1`` (no side effects)."""
    if not feedback_collector_enabled():
        return
    entry = {
        "ts": time.time(),
        "event_type": (event_type or "unknown").strip(),
        "session_id": (session_id or "").strip(),
        "payload": payload or {},
    }
    line = json.dumps(entry, ensure_ascii=False)
    with _lock:
        _recent.append(entry)
        try:
            with open(_events_path(), "a", encoding="utf-8") as f:
                f.write(line + "\n")
        except OSError:
            pass


def record_tool_outcome_feedback(
    tool_name: str,
    *,
    success: bool,
    duration_ms: float = 0.0,
    error_message: str = "",
    session_id: str = "",
) -> None:
    if success:
        return
    record_feedback_event(
        "tool_failure",
        {
            "tool_name": tool_name,
            "duration_ms": duration_ms,
            "error_message": (error_message or "")[:500],
        },
        session_id=session_id,
    )


def record_pipeline_close_feedback(
    pipeline_result: Dict[str, Any],
    *,
    session_id: str = "",
    task_name: str = "",
) -> None:
    degraded = pipeline_result.get("degraded_tools") or []
    errors = pipeline_result.get("errors") or []
    if not degraded and not errors:
        return
    record_feedback_event(
        "pipeline_close",
        {
            "task_name": (task_name or "")[:120],
            "degraded_tools": list(degraded)[:20],
            "error_count": len(errors) if isinstance(errors, list) else 0,
            "should_evolve": bool(pipeline_result.get("should_evolve")),
        },
        session_id=session_id,
    )


def record_analysis_artifact_feedback(
    artifact_path: str,
    *,
    session_id: str = "",
    task_name: str = "",
    degraded_tools: Optional[List[Any]] = None,
) -> None:
    if not artifact_path:
        return
    record_feedback_event(
        "analysis_artifact",
        {
            "artifact_path": artifact_path,
            "task_name": (task_name or "")[:120],
            "degraded_tools": list(degraded_tools or [])[:20],
        },
        session_id=session_id,
    )


def recent_feedback_events(limit: int = 20) -> List[Dict[str, Any]]:
    with _lock:
        return list(_recent)[-max(1, limit) :]


def reset_feedback_collector_state() -> None:
    """Test helper."""
    with _lock:
        _recent.clear()
