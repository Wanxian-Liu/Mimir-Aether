"""
E-007 — session-isolated execution pipeline state.

Replaces module-level singleton recorder with per-session registry + ContextVar
so concurrent agent runs do not clobber each other's trajectories.
"""

from __future__ import annotations

import uuid
from contextvars import ContextVar
from dataclasses import dataclass, field
from threading import Lock
from typing import Dict, List, Optional, TYPE_CHECKING

from .execution_recorder import ExecutionRecorder
from .tool_quality import ToolQualityManager

if TYPE_CHECKING:
    from .post_analysis import EvolutionSuggestion

_session_lock = Lock()
_sessions: Dict[str, "_PipelineSession"] = {}
_current_session_id: ContextVar[Optional[str]] = ContextVar(
    "execution_pipeline_session_id",
    default=None,
)


@dataclass
class _PipelineSession:
    recorder: ExecutionRecorder
    quality_mgr: Optional[ToolQualityManager]
    task_name: str
    pending_suggestions: List["EvolutionSuggestion"] = field(default_factory=list)


def _resolve_session_id(session_id: str = "", task_name: str = "") -> Optional[str]:
    if session_id:
        return session_id
    ctx = _current_session_id.get()
    if ctx:
        return ctx
    if task_name:
        with _session_lock:
            for sid, sess in _sessions.items():
                if sess.task_name == task_name:
                    return sid
    return None


def start_execution_pipeline(
    task_name: str = "",
    session_id: str = "",
    enable_quality: bool = True,
) -> ExecutionRecorder:
    sid = session_id or uuid.uuid4().hex[:12]
    with _session_lock:
        existing = _sessions.get(sid)
        if existing is not None:
            _current_session_id.set(sid)
            return existing.recorder

        quality_mgr = ToolQualityManager(enable_persistence=True) if enable_quality else None
        recorder = ExecutionRecorder(task_name=task_name, session_id=sid)
        _sessions[sid] = _PipelineSession(
            recorder=recorder,
            quality_mgr=quality_mgr,
            task_name=task_name or sid,
        )

    _current_session_id.set(sid)
    return recorder


def get_recorder(session_id: str = "") -> Optional[ExecutionRecorder]:
    sid = _resolve_session_id(session_id=session_id)
    if not sid:
        return None
    with _session_lock:
        sess = _sessions.get(sid)
    return sess.recorder if sess else None


def get_quality_manager(session_id: str = "") -> Optional[ToolQualityManager]:
    sid = _resolve_session_id(session_id=session_id)
    if not sid:
        return None
    with _session_lock:
        sess = _sessions.get(sid)
    return sess.quality_mgr if sess else None


def get_pipeline_session(session_id: str = "", task_name: str = "") -> Optional[_PipelineSession]:
    sid = _resolve_session_id(session_id=session_id, task_name=task_name)
    if not sid:
        return None
    with _session_lock:
        return _sessions.get(sid)


def close_execution_pipeline(
    task_name: str = "",
    session_id: str = "",
) -> Optional[_PipelineSession]:
    sid = _resolve_session_id(session_id=session_id, task_name=task_name)
    if not sid:
        return None
    with _session_lock:
        return _sessions.pop(sid, None)


def reset_execution_pipeline_state() -> None:
    """Test helper — clear all session state."""
    with _session_lock:
        _sessions.clear()
    _current_session_id.set(None)
