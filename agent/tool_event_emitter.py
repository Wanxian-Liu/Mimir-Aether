"""Minimal tool execution event emitter.

Emits tool_execution_start / tool_execution_end events that gateway
platforms (Feishu, Telegram, etc.) can subscribe to for real-time
status updates like "read_file executing..." → "read_file done".

Usage (agent loop):
    from agent.tool_event_emitter import emit_tool_execution_start, emit_tool_execution_end

    emit_tool_execution_start(tool_name, arguments, session_id)
    try:
        result = await run_tool(...)
        emit_tool_execution_end(tool_name, success=True, session_id=duration_ms=...)
    except Exception:
        emit_tool_execution_end(tool_name, success=False, session_id=..., error=...)

Usage (gateway subscriber):
    from agent.tool_event_emitter import subscribe

    def on_tool_event(event: dict):
        if event["type"] == "tool_execution_start":
            # Update UI: "🔧 tool_name running..."
    token = subscribe(on_tool_event)  # returns unsubscribe callable

Env guard: only emits when MIMIR_TOOL_EVENTS=1 (default off).
"""

from __future__ import annotations

import os
import time
from typing import Any, Callable, Dict, List

_ToolEventCallback = Callable[[Dict[str, Any]], None]
_subscribers: List[_ToolEventCallback] = []


def _env_on() -> bool:
    return os.environ.get("MIMIR_TOOL_EVENTS", "").strip() in ("1", "true", "yes")


def subscribe(callback: _ToolEventCallback) -> Callable[[], None]:
    """Register a callback that receives tool event dicts.

    Returns a zero-arg callable to unsubscribe.
    """
    _subscribers.append(callback)

    def _unsubscribe() -> None:
        try:
            _subscribers.remove(callback)
        except ValueError:
            pass

    return _unsubscribe


def emit_tool_execution_start(
    tool_name: str,
    arguments: Dict[str, Any] = None,
    session_id: str = "",
) -> None:
    """Emit tool_execution_start event to all subscribers."""
    if not _env_on():
        return
    _emit(
        {
            "type": "tool_execution_start",
            "tool_name": tool_name,
            "arguments": arguments or {},
            "session_id": session_id,
            "timestamp": time.time(),
        }
    )


def emit_tool_execution_end(
    tool_name: str,
    *,
    success: bool = True,
    duration_ms: float = 0.0,
    session_id: str = "",
    error: str = "",
) -> None:
    """Emit tool_execution_end event to all subscribers."""
    if not _env_on():
        return
    _emit(
        {
            "type": "tool_execution_end",
            "tool_name": tool_name,
            "success": success,
            "duration_ms": duration_ms,
            "session_id": session_id,
            "error": error,
            "timestamp": time.time(),
        }
    )


def _emit(event: Dict[str, Any]) -> None:
    for cb in list(_subscribers):
        try:
            cb(event)
        except Exception:
            pass  # subscriber error never breaks emitter
