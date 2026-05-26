"""Aggregate recent feedback events into tune inputs (IQ-EVO Wave 5)."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List

from mimir_constants import get_mimir_home


def _feedback_path() -> Path:
    return Path(get_mimir_home()) / "data" / "feedback_events.jsonl"


def summarize_recent_experience(*, max_lines: int = 200) -> Dict[str, Any]:
    """Read tail of feedback_events.jsonl; empty dict if missing."""
    path = _feedback_path()
    if not path.is_file():
        return {
            "event_count": 0,
            "tool_failure_count": 0,
            "pipeline_close_count": 0,
            "analysis_artifact_count": 0,
            "top_failed_tools": [],
        }
    try:
        lines = path.read_text(encoding="utf-8").strip().splitlines()
    except OSError:
        return {"event_count": 0, "tool_failure_count": 0, "pipeline_close_count": 0}

    tail = lines[-max(1, max_lines) :]
    types: Counter[str] = Counter()
    tools: Counter[str] = Counter()
    for line in tail:
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        et = str(row.get("event_type") or "")
        types[et] += 1
        if et == "tool_failure":
            payload = row.get("payload") or {}
            name = str(payload.get("tool_name") or "")
            if name:
                tools[name] += 1

    return {
        "event_count": sum(types.values()),
        "tool_failure_count": types.get("tool_failure", 0),
        "pipeline_close_count": types.get("pipeline_close", 0),
        "analysis_artifact_count": types.get("analysis_artifact", 0),
        "top_failed_tools": [t for t, _ in tools.most_common(5)],
    }
