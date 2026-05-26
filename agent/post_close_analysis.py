"""Post-close LLM execution analysis (IQ-EVO-07 / ``MIMIR_AUTO_ANALYSIS=1``)."""

from __future__ import annotations

import logging
import os
import threading
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

_ANALYSIS_SYSTEM = (
    "You analyze agent execution traces for evolution opportunities. "
    "Return JSON only with keys: summary (string), overall_rating (0-10 number), "
    "tool_issues (string array), suggestions (array of objects with target, action, "
    "reason, priority 1-5, confidence 0-1, suggested_changes)."
)


def _env_truthy(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in ("1", "true", "yes")


def _pipeline_has_analysis_signal(pipeline_result: Dict[str, Any]) -> bool:
    if pipeline_result.get("errors"):
        return True
    if pipeline_result.get("degraded_tools"):
        return True
    return False


def _extract_llm_text(response: Any) -> str:
    try:
        return (response.choices[0].message.content or "").strip()
    except (AttributeError, IndexError, TypeError):
        return ""


def run_post_analysis_sync(
    pipeline_result: Dict[str, Any],
    *,
    task_name: str = "",
    session_id: str = "",
) -> Optional[str]:
    """Run analysis when env is on and pipeline has errors/degraded tools.

    Returns a skip reason, or ``None`` when analysis ran (or artifact-only path).
    """
    if not _env_truthy("MIMIR_AUTO_ANALYSIS"):
        return "env_off"
    if not _pipeline_has_analysis_signal(pipeline_result):
        return "no_signal"

    from agent.execution_pipeline import (
        apply_analysis_to_pipeline,
        build_analysis_from_pipeline,
        save_analysis_artifact,
    )

    prompt = build_analysis_from_pipeline(pipeline_result, task_name)
    if not prompt:
        return "no_trajectory"

    artifact_path = save_analysis_artifact(prompt, task_name)
    try:
        from agent.feedback_collector import record_analysis_artifact_feedback

        record_analysis_artifact_feedback(
            artifact_path or "",
            session_id=session_id,
            task_name=task_name,
            degraded_tools=pipeline_result.get("degraded_tools"),
        )
    except Exception:
        pass

    try:
        from agent.auxiliary_client import call_llm

        response = call_llm(
            task="compression",
            messages=[
                {"role": "system", "content": _ANALYSIS_SYSTEM},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
            max_tokens=4096,
        )
        raw = _extract_llm_text(response)
        if not raw:
            return "empty_llm"
        apply_analysis_to_pipeline(raw, session_id=session_id, task_name=task_name)
        logger.info(
            "post_analysis applied session_id=%s task=%s",
            session_id,
            (task_name or "")[:40],
        )
        return None
    except Exception as exc:
        logger.warning(
            "post_analysis LLM failed session_id=%s: %s",
            session_id,
            exc,
        )
        return "llm_failed"


def schedule_post_close_analysis(
    pipeline_result: Dict[str, Any],
    *,
    task_name: str = "",
    session_id: str = "",
) -> None:
    """Fire-and-forget post-close analysis (does not block the agent loop)."""
    if not _env_truthy("MIMIR_AUTO_ANALYSIS"):
        return

    def _worker() -> None:
        try:
            reason = run_post_analysis_sync(
                pipeline_result,
                task_name=task_name,
                session_id=session_id,
            )
            if reason and reason not in ("env_off",):
                logger.info(
                    "post_analysis skipped reason=%s session_id=%s",
                    reason,
                    session_id,
                )
        except Exception as exc:
            logger.warning(
                "post_analysis worker failed session_id=%s: %s",
                session_id,
                exc,
            )

    threading.Thread(
        target=_worker,
        daemon=True,
        name="post-close-analysis",
    ).start()


__all__ = [
    "run_post_analysis_sync",
    "schedule_post_close_analysis",
]
