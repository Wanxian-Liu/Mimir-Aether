"""
OpenSpace-inspired execution analysis pipeline — lightweight integration.

Wires together:
  - ExecutionRecorder  (recording layer)
  - ToolQualityManager (quality tracking)
  - PostExecutionAnalyzer (LLM analysis + evolution suggestions)

This module is the "glue" that connects MimirAether's existing agent loop
to the self-evolution feedback loop.

Usage in agent_loop.py (finally block after task completion):
    from agent.execution_pipeline import close_execution_pipeline
    analysis = await close_execution_pipeline(recorder, quality_mgr, session)

Design: All components are optional — if recording or quality tracking is
disabled, the pipeline degrades gracefully.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from .execution_recorder import ExecutionRecorder, extract_errors, generate_summary
from .execution_pipeline_sessions import (
    close_execution_pipeline as _pop_session,
    get_quality_manager,
    get_recorder,
    start_execution_pipeline,
)
from .tool_quality import ToolQualityManager
from .post_analysis import (
    ExecutionAnalysis,
    EvolutionSuggestion,
    build_analysis_prompt,
    parse_analysis_result,
)
from .skill_evolution import build_confirmation_prompt, parse_confirmation
from .conversation_formatter import format_trajectory_for_analysis


def record_tool_call(
    tool_name: str,
    arguments: Dict[str, Any] = None,
    *,
    success: bool = True,
    error_message: str = "",
    duration_ms: float = 0.0,
    result_summary: str = "",
    session_id: str = "",
) -> None:
    """Record one tool execution in both recorder and quality manager."""
    recorder = get_recorder(session_id=session_id)
    if recorder:
        recorder.record_tool_call(
            tool_name=tool_name,
            arguments=arguments,
            success=success,
            error_message=error_message,
            duration_ms=duration_ms,
            result_summary=result_summary,
        )

    quality_mgr = get_quality_manager(session_id=session_id)
    if quality_mgr:
        quality_mgr.record(
            tool_name=tool_name,
            success=success,
            error_message=error_message,
            duration_ms=duration_ms,
        )


def close_execution_pipeline(
    task_name: str = "",
    session_id: str = "",
) -> Dict[str, Any]:
    """Finalize recording and generate analysis-ready data."""
    result: Dict[str, Any] = {
        "trajectory_path": "",
        "summary": {},
        "errors": [],
        "quality_report": {},
        "should_evolve": False,
        "degraded_tools": [],
    }

    session = _pop_session(task_name=task_name, session_id=session_id)
    if session and session.recorder:
        session.recorder.close()
        result["trajectory_path"] = str(session.recorder.file_path)
        result["summary"] = generate_summary(session.recorder.file_path)
        result["errors"] = extract_errors(session.recorder.file_path)

    if session and session.quality_mgr:
        result["quality_report"] = session.quality_mgr.get_report()
        result["should_evolve"] = session.quality_mgr.should_evolve()
        result["degraded_tools"] = session.quality_mgr.get_degraded_tools()

    return result


def build_analysis_from_pipeline(
    pipeline_result: Dict[str, Any],
    task_name: str = "",
) -> Optional[str]:
    """Build an analysis prompt from pipeline results."""
    trajectory_path = pipeline_result.get("trajectory_path", "")
    if not trajectory_path or not Path(trajectory_path).exists():
        return None

    trace_text = format_trajectory_for_analysis(str(trajectory_path))
    quality_data = pipeline_result.get("quality_report", {})

    return build_analysis_prompt(
        trace_text=trace_text,
        tool_quality=quality_data,
        task_name=task_name,
    )


def apply_analysis_to_pipeline(
    analysis_json: str,
    session_id: str = "",
    task_name: str = "",
) -> ExecutionAnalysis:
    """Parse LLM analysis result and apply suggestions to quality manager."""
    analysis = parse_analysis_result(analysis_json, session_id=session_id, task_name=task_name)

    recorder = get_recorder(session_id=session_id)
    if recorder:
        recorder.record_analysis(
            analysis_type="post_execution",
            findings=analysis.summary,
            evolution_suggestions=[s.to_dict() for s in analysis.suggestions],  # type: ignore
        )

    quality_mgr = get_quality_manager(session_id=session_id)
    if quality_mgr:
        for suggestion in analysis.suggestions:
            if suggestion.action in ("fix", "deprecate"):
                quality_mgr.flag_llm_issue(suggestion.target)

    return analysis


def maybe_trigger_post_analysis(
    pipeline_result: Dict[str, Any],
    task_name: str = "",
    *,
    min_errors: int = 1,
) -> Optional[str]:
    """Check if post-task analysis should run, and format the prompt if so."""
    errors = pipeline_result.get("errors", [])
    if not errors or len(errors) < min_errors:
        return None

    return build_analysis_from_pipeline(pipeline_result, task_name)


def save_analysis_artifact(
    prompt: str,
    task_name: str = "",
) -> Optional[str]:
    """Persist an analysis prompt as a JSON artifact for next-session injection."""
    from .mimir_constants import get_mimir_home

    home = get_mimir_home()
    artifacts_dir = Path(home) / "data" / "analysis_artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    import datetime as _dt
    ts = _dt.datetime.now().strftime("%Y%m%dT%H%M%S")
    safe_name = task_name.replace("/", "_").replace(" ", "_")[:60] if task_name else "unnamed"
    filename = f"{ts}_{safe_name}.json"

    artifact = {
        "task_name": task_name,
        "timestamp": _dt.datetime.now().isoformat(),
        "prompt": prompt,
        "type": "post_task_analysis",
    }

    path = artifacts_dir / filename
    path.write_text(json.dumps(artifact, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(path)


__all__ = [
    "start_execution_pipeline",
    "get_recorder",
    "get_quality_manager",
    "record_tool_call",
    "close_execution_pipeline",
    "build_analysis_from_pipeline",
    "apply_analysis_to_pipeline",
    "maybe_trigger_post_analysis",
    "save_analysis_artifact",
]
