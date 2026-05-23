"""E-012 post-pipeline JEPA run_cycle hook (env-gated, default safe)."""

from __future__ import annotations

import logging
import os
import threading
from typing import Any, Dict, List, Optional

from agent.self_evolution.engine import get_engine

logger = logging.getLogger(__name__)

_MAX_CANDIDATES = 5

# key = normalized tool/module alias; value = agent/ relative path
_TOOL_AGENT_FILES: dict[str, str] = {
    "skill_evolution": "skill_evolution.py",
    "execution_recorder": "execution_recorder.py",
    "tool_quality": "tool_quality.py",
    "post_analysis": "post_analysis.py",
    "execution_pipeline": "execution_pipeline.py",
}


def _truthy(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in ("1", "true", "yes")


def _tool_to_agent_file(tool_name: str) -> Optional[str]:
    if not tool_name:
        return None
    key = tool_name.strip()
    if key in _TOOL_AGENT_FILES:
        return _TOOL_AGENT_FILES[key]
    key_norm = key.lower().replace("-", "_")
    return _TOOL_AGENT_FILES.get(key_norm)


def derive_jepa_candidates(pipeline_result: dict) -> list[str]:
    """
    Derive candidate agent-relative files from close_execution_pipeline output.

    v1: registry tool names (e.g. read_file) usually do not map; infra fallback
    or no_candidates smoke logs are expected when only unmapped tools appear.
    """
    seen: set[str] = set()
    out: list[str] = []

    def add(path: Optional[str]) -> None:
        if not path or path in seen:
            return
        seen.add(path)
        out.append(path)

    for tool_name, _score in pipeline_result.get("degraded_tools") or []:
        add(_tool_to_agent_file(str(tool_name)))

    for err in (pipeline_result.get("errors") or [])[:3]:
        if isinstance(err, dict):
            add(_tool_to_agent_file(str(err.get("tool_name", ""))))

    for sug in pipeline_result.get("evolution_suggestions") or []:
        if not isinstance(sug, dict):
            continue
        target = str(sug.get("target", ""))
        if target.endswith(".py") and "agent/" in target:
            idx = target.find("agent/")
            add(target[idx + len("agent/") :])

    if out:
        return out[:_MAX_CANDIDATES]

    has_signal = bool(
        pipeline_result.get("should_evolve")
        or pipeline_result.get("errors")
        or pipeline_result.get("degraded_tools")
    )
    if has_signal:
        for fallback in ("execution_pipeline.py", "tool_quality.py"):
            add(fallback)
        return out[:_MAX_CANDIDATES]

    return []


def run_jepa_cycle_sync(
    pipeline_result: Dict[str, Any],
    *,
    session_id: str = "",
) -> Optional[str]:
    """Return skip reason (env_off / no_candidates) or None when run_cycle executed."""
    if not _truthy("MIMIR_JEPA_CYCLE"):
        return "env_off"

    candidates = derive_jepa_candidates(pipeline_result)
    if not candidates:
        logger.info(
            "jepa_cycle skipped reason=no_candidates session_id=%s",
            session_id,
        )
        return "no_candidates"

    report = get_engine().run_cycle(
        candidates,
        execute_callback=None,
        run_tier0=_truthy("MIMIR_JEPA_RUN_TIER0"),
    )
    logger.info(
        "jepa_cycle done status=%s cycle_time_ms=%s candidates=%s session_id=%s",
        getattr(report, "status", "?"),
        getattr(report, "cycle_time_ms", 0),
        len(candidates),
        session_id,
    )
    return None


def schedule_post_close_jepa_cycle(
    pipeline_result: Dict[str, Any],
    *,
    session_id: str = "",
) -> None:
    if not _truthy("MIMIR_JEPA_CYCLE"):
        return

    def _worker() -> None:
        try:
            run_jepa_cycle_sync(pipeline_result, session_id=session_id)
        except Exception as exc:
            logger.warning(
                "jepa_cycle worker failed session_id=%s: %s",
                session_id,
                exc,
            )

    threading.Thread(target=_worker, daemon=True, name="jepa-cycle").start()
