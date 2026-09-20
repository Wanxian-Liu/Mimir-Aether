"""Structured feedback events (IQ-EVO Wave 4 · record-only, no threshold mutation).

开关语义组纪律（铁律二 · IQ 批2 · 2026-09-20）
---------------------------------------------
本模块属 **量具组**（record-only：只 append JSONL，零写副作用）。
它 **不得** 与 **执行器组**（可写 SKILL.md / tuned_thresholds / 1c policy）
编入同一个运维批量改键动作。

实证代价：2026-08-16 13:41 一次「关自动进化」运维把下面 **两组共 4 个键** 一起改成 0
（备份名 autoevolve-off-20260816）⇒ 采集器停摆 **5 周**（末条事件 2026-08-16 13:44:25），
而停摆期间的「零事件」被下游（auto_tuner / IQ 评分表）读成「零失败」
—— 量具坏掉会静默表现为「没有反馈」。

分层语义：采集层常开（零写副作用）｜分析层可开但只产 artifact；
应用层人工审 + 白名单；框架层 agent/*.py 机器硬禁。
"""

from __future__ import annotations

import json
import os
import threading
import time
from collections import deque
from pathlib import Path
from typing import Any, Deque, Dict, List, Optional, Tuple

from mimir_constants import get_mimir_home

_lock = threading.Lock()
_recent: Deque[Dict[str, Any]] = deque(maxlen=200)

# ── 开关语义组 · 单一真源（IQ 批2 · 2026-09-20）─────────────────────────
# 量具组（只读采集，常开）与执行器组（可写，维持 0）**互斥**：
# 批量改键时必须按组分开，禁止跨组一把改（见模块 docstring 实证）。
INSTRUMENT_ENV_KEYS: Tuple[str, ...] = ("MIMIR_FEEDBACK_COLLECTOR",)
EXECUTOR_ENV_KEYS: Tuple[str, ...] = (
    "MIMIR_AUTO_ANALYSIS",
    "MIMIR_AUTO_EVOLVE",
    "MIMIR_AUTO_TUNER",
    "MIMIR_AUTO_1C_POLICY",
)


def switch_semantics() -> Dict[str, Any]:
    """两组开关的机器可读字典（运维 / 告警 / 评分共用）。"""
    return {
        "instrument": {
            "keys": list(INSTRUMENT_ENV_KEYS),
            "writes": "record-only (append-only JSONL)",
            "policy": "常开",
        },
        "executor": {
            "keys": list(EXECUTOR_ENV_KEYS),
            "writes": "SKILL.md / tuned_thresholds / 1c policy (可写)",
            "policy": "维持 0 · 分层授权后再开",
        },
        "disjoint": not (set(INSTRUMENT_ENV_KEYS) & set(EXECUTOR_ENV_KEYS)),
    }




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
