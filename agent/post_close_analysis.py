"""Post-close LLM execution analysis (IQ-EVO-07 / ``MIMIR_AUTO_ANALYSIS=1``)."""

from __future__ import annotations

import logging
import os
import threading
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_ANALYSIS_SYSTEM = (
    "You analyze agent execution traces for evolution opportunities. "
    "Return JSON only with keys: summary (string), overall_rating (0-10 number), "
    "tool_issues (string array), suggestions (array of objects with target, action, "
    "reason, priority 1-5, confidence 0-1, suggested_changes)."
)


def _env_truthy(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in ("1", "true", "yes")


def _has_fix_or_deprecate_suggestions(suggestions: List[Any]) -> bool:
    return any(getattr(s, "action", None) in ("fix", "deprecate") for s in suggestions)


def maybe_fallback_evolution_suggestions(
    analysis: Any,
    pipeline_result: Dict[str, Any],
) -> Any:
    """When LLM returns no fix/deprecate but pipeline has errors, add one fix suggestion."""
    from agent.post_analysis import EvolutionSuggestion

    if _has_fix_or_deprecate_suggestions(analysis.suggestions):
        return analysis

    errors = pipeline_result.get("errors") or []
    if not errors:
        return analysis

    first = errors[0]
    if isinstance(first, dict):
        tool_name = (
            first.get("tool_name")
            or first.get("tool")
            or first.get("name")
            or "unknown"
        )
    else:
        tool_name = "unknown"

    analysis.suggestions.append(
        EvolutionSuggestion(
            target=str(tool_name),
            action="fix",
            reason="iqevo-48 fallback: pipeline errors without LLM suggestions",
            priority=3,
            confidence=0.5,
            suggested_changes="Review tool failure and update skill guidance.",
        )
    )
    return analysis


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
        _run_post_analysis_tail(pipeline_result, session_id=session_id, task_name=task_name)
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
            _run_post_analysis_tail(pipeline_result, session_id=session_id, task_name=task_name)
            return "empty_llm"
        analysis = apply_analysis_to_pipeline(
            raw, session_id=session_id, task_name=task_name
        )
        analysis = maybe_fallback_evolution_suggestions(analysis, pipeline_result)
        logger.info(
            "post_analysis applied session_id=%s task=%s",
            session_id,
            (task_name or "")[:40],
        )
        try:
            from agent.execution_pipeline import apply_evolution_from_analysis

            evo_results = apply_evolution_from_analysis(analysis)
            if evo_results:
                ok_n = sum(1 for r in evo_results if r.success)
                logger.info(
                    "post_analysis evolution session_id=%s applied=%s ok=%s",
                    session_id,
                    len(evo_results),
                    ok_n,
                )
                if ok_n < len(evo_results):
                    for r in evo_results:
                        if not r.success and r.error:
                            logger.info(
                                "post_analysis evolution detail session_id=%s "
                                "target=%s action=%s error=%s",
                                session_id,
                                r.target,
                                getattr(r.action, "value", r.action),
                                (r.error or "")[:200],
                            )
        except Exception as exc:
            logger.warning(
                "post_analysis evolution failed session_id=%s: %s",
                session_id,
                exc,
            )
        _run_post_analysis_tail(pipeline_result, session_id=session_id, task_name=task_name)
        return None
    except Exception as exc:
        logger.warning(
            "post_analysis LLM failed session_id=%s: %s",
            session_id,
            exc,
        )
        _run_post_analysis_tail(pipeline_result, session_id=session_id, task_name=task_name)
        return "llm_failed"


def _run_post_analysis_tail(
    pipeline_result: Dict[str, Any],
    *,
    session_id: str = "",
    task_name: str = "",
) -> None:
    """Tune (1b) then 1c policy nudge — boundary B-4 after analysis/evolve."""
    try:
        from agent.decision_compressor_policy import run_tune_and_1c_after_post_analysis

        run_tune_and_1c_after_post_analysis(
            pipeline_result,
            session_id=session_id,
            task_name=task_name,
        )
    except Exception as exc:
        logger.warning(
            "post_analysis tune/1c failed session_id=%s: %s",
            session_id,
            exc,
        )


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
    "maybe_fallback_evolution_suggestions",
]
