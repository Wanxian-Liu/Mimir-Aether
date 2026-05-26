"""Bounded threshold tuning from feedback (IQ-EVO Wave 5 · 1b)."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from mimir_constants import get_mimir_home

from .experience_buffer import summarize_recent_experience
from .tuned_thresholds import get_tuned_float, get_tuned_int, set_override


def auto_tuner_enabled() -> bool:
    return os.environ.get("MIMIR_AUTO_TUNER", "").strip().lower() in (
        "1",
        "true",
        "yes",
    )


def _audit_path() -> Path:
    path = Path(get_mimir_home()) / "data" / "tune_audit.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _append_audit(entry: Dict[str, Any]) -> None:
    try:
        with open(_audit_path(), "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError:
        pass


def run_tune_after_pipeline_close(
    pipeline_result: Dict[str, Any],
    *,
    session_id: str = "",
) -> List[Dict[str, Any]]:
    """Apply at most one bounded nudge per key when signals warrant it."""
    if not auto_tuner_enabled():
        return []

    summary = summarize_recent_experience()
    degraded = pipeline_result.get("degraded_tools") or []
    errors = pipeline_result.get("errors") or []
    error_count = len(errors) if isinstance(errors, list) else 0
    degraded_count = len(degraded) if isinstance(degraded, list) else 0

    changes: List[Dict[str, Any]] = []

    # More tool failures → compress slightly earlier (lower threshold_percent).
    if summary.get("tool_failure_count", 0) >= 3 or error_count >= 2:
        key = "compressor.threshold_percent"
        cur = get_tuned_float(key)
        new_val = cur - 0.05
        if new_val < cur:
            entry = set_override(
                key,
                new_val,
                reason=f"tool_failures={summary.get('tool_failure_count')} errors={error_count}",
            )
            entry["session_id"] = session_id
            changes.append(entry)
            _append_audit(entry)

    # Repeated failures → more sensitive loop detection (lower repeat threshold).
    if summary.get("tool_failure_count", 0) >= 5:
        key = "degeneration.loop_detection.threshold"
        cur = get_tuned_int(key)
        if cur > 2:
            entry = set_override(
                key,
                cur - 1,
                reason=f"tool_failures={summary.get('tool_failure_count')}",
            )
            entry["session_id"] = session_id
            changes.append(entry)
            _append_audit(entry)

    # Many degraded tools → surface more in prompt (lower quality bar).
    if degraded_count >= 2 or summary.get("pipeline_close_count", 0) >= 2:
        key = "tool_quality.degraded_threshold"
        cur = get_tuned_float(key)
        new_val = cur - 0.05
        if new_val < cur:
            entry = set_override(
                key,
                new_val,
                reason=f"degraded={degraded_count} pipeline_closes={summary.get('pipeline_close_count')}",
            )
            entry["session_id"] = session_id
            changes.append(entry)
            _append_audit(entry)

    return changes
