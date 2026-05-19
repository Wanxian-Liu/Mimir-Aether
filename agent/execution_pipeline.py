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
from .tool_quality import ToolQualityManager
from .post_analysis import (
    ExecutionAnalysis,
    EvolutionSuggestion,
    build_analysis_prompt,
    parse_analysis_result,
)
from .skill_evolution import build_confirmation_prompt, parse_confirmation
from .conversation_formatter import format_trajectory_for_analysis

# ── Global state (optional, per-session) ────────────────────────────────────

_active_recorder: Optional[ExecutionRecorder] = None
_active_quality_mgr: Optional[ToolQualityManager] = None


def start_execution_pipeline(
    task_name: str = "",
    session_id: str = "",
    enable_quality: bool = True,
) -> ExecutionRecorder:
    """Initialize recording and quality tracking for a task execution.

    Called at the start of execute() in agent_loop.py.
    """
    global _active_recorder, _active_quality_mgr

    _active_recorder = ExecutionRecorder(task_name=task_name, session_id=session_id)

    if enable_quality and _active_quality_mgr is None:
        _active_quality_mgr = ToolQualityManager(enable_persistence=True)

    return _active_recorder


def get_recorder() -> Optional[ExecutionRecorder]:
    """Get the active recorder (or None if pipeline not started)."""
    return _active_recorder


def get_quality_manager() -> Optional[ToolQualityManager]:
    """Get the active quality manager (or None)."""
    return _active_quality_mgr


def record_tool_call(
    tool_name: str,
    arguments: Dict[str, Any] = None,
    *,
    success: bool = True,
    error_message: str = "",
    duration_ms: float = 0.0,
    result_summary: str = "",
) -> None:
    """Record one tool execution in both recorder and quality manager.

    Called after each tool call in the agent loop.
    """
    if _active_recorder:
        _active_recorder.record_tool_call(
            tool_name=tool_name,
            arguments=arguments,
            success=success,
            error_message=error_message,
            duration_ms=duration_ms,
            result_summary=result_summary,
        )

    if _active_quality_mgr:
        _active_quality_mgr.record(
            tool_name=tool_name,
            success=success,
            error_message=error_message,
            duration_ms=duration_ms,
        )


def close_execution_pipeline(
    task_name: str = "",
) -> Dict[str, Any]:
    """Finalize recording and generate analysis-ready data.

    Called in the finally block after task execution completes.

    Returns a dict with:
      - trajectory_path: Path to the JSONL recording
      - summary: Execution summary stats
      - errors: List of failed tool calls
      - quality_report: Tool quality report (if quality tracking enabled)
      - should_evolve: Whether evolution threshold was reached
      - degraded_tools: Tools below quality threshold
    """
    global _active_recorder, _active_quality_mgr

    result: Dict[str, Any] = {
        "trajectory_path": "",
        "summary": {},
        "errors": [],
        "quality_report": {},
        "should_evolve": False,
        "degraded_tools": [],
    }

    # Close recorder
    if _active_recorder:
        _active_recorder.close()
        result["trajectory_path"] = str(_active_recorder.file_path)
        result["summary"] = generate_summary(_active_recorder.file_path)
        result["errors"] = extract_errors(_active_recorder.file_path)
        _active_recorder = None

    # Quality check
    if _active_quality_mgr:
        result["quality_report"] = _active_quality_mgr.get_report()
        result["should_evolve"] = _active_quality_mgr.should_evolve()
        result["degraded_tools"] = _active_quality_mgr.get_degraded_tools()

    return result


def build_analysis_from_pipeline(
    pipeline_result: Dict[str, Any],
    task_name: str = "",
) -> Optional[str]:
    """Build an analysis prompt from pipeline results.

    Uses priority-based conversation formatter for compact analysis prompts.
    Returns the prompt string to send to the LLM, or None if insufficient data.
    """
    trajectory_path = pipeline_result.get("trajectory_path", "")
    if not trajectory_path or not Path(trajectory_path).exists():
        return None

    # Format trajectory using priority-based truncation
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

    # Record analysis in recorder if active
    if _active_recorder:
        _active_recorder.record_analysis(
            analysis_type="post_execution",
            findings=analysis.summary,
            evolution_suggestions=[s.to_dict() for s in analysis.suggestions],  # type: ignore
        )

    # Flag degraded tools
    if _active_quality_mgr:
        for suggestion in analysis.suggestions:
            if suggestion.action in ("fix", "deprecate"):
                _active_quality_mgr.flag_llm_issue(suggestion.target)

    return analysis


# ── Post-task analysis trigger ──────────────────────────────────────────

def maybe_trigger_post_analysis(
    pipeline_result: Dict[str, Any],
    task_name: str = "",
    *,
    min_errors: int = 1,
) -> Optional[str]:
    """Check if post-task analysis should run, and format the prompt if so.

    Self-designed for MimirAether — learned the trigger-point pattern from
    OpenSpace (tool_layer._maybe_analyze_execution) but implemented natively
    on our execution_pipeline + conversation_formatter.

    Trigger conditions (MimirAether-specific):
      - At least *min_errors* tool errors in the pipeline result
      - A trajectory file exists and is readable

    Returns:
        Analysis prompt string ready for LLM consumption, or None if
        conditions not met.  Caller decides whether to call the LLM —
        this function is provider-agnostic.

    Usage in agent caller (after loop completes)::

        pipeline_result = close_execution_pipeline(task_name)
        prompt = maybe_trigger_post_analysis(pipeline_result, task_name)
        if prompt:
            artifact_path = save_analysis_artifact(prompt, task_name)
    """
    errors = pipeline_result.get("errors", [])
    if not errors or len(errors) < min_errors:
        return None

    return build_analysis_from_pipeline(pipeline_result, task_name)


def save_analysis_artifact(
    prompt: str,
    task_name: str = "",
) -> Optional[str]:
    """Persist an analysis prompt as a JSON artifact for next-session injection.

    Artifacts are stored under ``<MIMIR_AETHER_HOME>/data/analysis_artifacts/``
    and can be injected into the system prompt of future sessions so the agent
    learns from past mistakes without burning tokens mid-task.
    """
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
