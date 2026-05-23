"""
Execution Recorder — Records agent tool execution traces for post-hoc analysis.

Learned from OpenSpace recording/ (recorder.py + action_recorder.py):
  - Append-only JSONL (crash-safe, no partial writes)
  - Dual-layer recording: tool-level (trajectory) + agent-level (actions)
  - Structured metadata for downstream evolution analysis

Three record types:
  TOOL_CALL   — one tool execution (call + result)
  AGENT_ACTION — agent decision/planning step
  ANALYSIS    — post-execution LLM analysis result

Design: Lightweight, zero-dependency beyond stdlib.  Persists to
<MIMIR_AETHER_HOME>/data/trajectories/YYYY-MM-DD/<session_id>.jsonl
"""

from __future__ import annotations

import json
import os
import time
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


def _get_trajectory_dir() -> Path:
    """Resolve trajectory storage directory."""
    home = os.getenv("MIMIR_AETHER_HOME", os.path.expanduser("~/.mimiraether"))
    return Path(home) / "data" / "trajectories"


def _today_dir() -> Path:
    return _get_trajectory_dir() / datetime.now(timezone.utc).strftime("%Y-%m-%d")


# ── Data types ──────────────────────────────────────────────────────────────

@dataclass
class ToolCallRecord:
    """One tool execution trace."""
    step: int
    tool_name: str
    arguments: Dict[str, Any] = field(default_factory=dict)
    result_summary: str = ""          # first 200 chars of result
    success: bool = True
    error_message: str = ""
    duration_ms: float = 0.0
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()


@dataclass
class AgentActionRecord:
    """One agent decision step."""
    step: int
    action_type: str                  # plan | reasoning | evaluate | select
    summary: str = ""                 # brief description (<200 chars)
    model_used: str = ""
    token_count: int = 0
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()


@dataclass
class AnalysisRecord:
    """Post-execution LLM analysis result (added after task completes)."""
    step: int
    analysis_type: str                # quality | evolution | summary
    findings: str = ""
    evolution_suggestions: List[str] = field(default_factory=list)
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()


# ── Recorder ────────────────────────────────────────────────────────────────

class ExecutionRecorder:
    """Append-only JSONL recorder for agent execution traces.

    Usage::

        recorder = ExecutionRecorder("task_name")
        recorder.record_tool_call("web_search", {"query": "..."}, success=True)
        recorder.record_agent_action("plan", "Decided to search first")
        # ... after task completes ...
        recorder.close()

    The JSONL file can then be fed to the analysis pipeline.
    """

    def __init__(self, task_name: str = "", session_id: str = ""):
        self._task_name = task_name or "unnamed"
        self._session_id = session_id or uuid.uuid4().hex[:12]
        self._step_counter = 0
        self._start_time = time.monotonic()
        self._start_ts = datetime.now(timezone.utc).isoformat()

        # Ensure directory
        _today_dir().mkdir(parents=True, exist_ok=True)

        self._file_path = _today_dir() / f"{self._session_id}.jsonl"

        # Fresh session file (avoid appending to stale trajectories on session reuse)
        with open(self._file_path, "w", encoding="utf-8") as f:
            f.write(
                json.dumps(
                    {
                        "type": "session_start",
                        "session_id": self._session_id,
                        "task_name": self._task_name,
                        "start_time": self._start_ts,
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )
            f.flush()
            os.fsync(f.fileno())

    # ── Public API ──────────────────────────────────────────────────────

    def record_tool_call(
        self,
        tool_name: str,
        arguments: Dict[str, Any] = None,
        *,
        success: bool = True,
        error_message: str = "",
        duration_ms: float = 0.0,
        result_summary: str = "",
    ) -> int:
        """Record one tool execution. Returns step number."""
        self._step_counter += 1
        rec = ToolCallRecord(
            step=self._step_counter,
            tool_name=tool_name,
            arguments=arguments or {},
            result_summary=result_summary[:200],
            success=success,
            error_message=error_message[:500],
            duration_ms=duration_ms,
        )
        self._write_line({"type": "tool_call", **asdict(rec)})
        return self._step_counter

    def record_agent_action(
        self,
        action_type: str,
        summary: str = "",
        *,
        model_used: str = "",
        token_count: int = 0,
    ) -> int:
        """Record one agent decision step."""
        self._step_counter += 1
        rec = AgentActionRecord(
            step=self._step_counter,
            action_type=action_type,
            summary=summary[:200],
            model_used=model_used,
            token_count=token_count,
        )
        self._write_line({"type": "agent_action", **asdict(rec)})
        return self._step_counter

    def record_analysis(
        self,
        analysis_type: str,
        findings: str = "",
        *,
        evolution_suggestions: List[str] = None,
    ) -> int:
        """Record post-execution analysis."""
        self._step_counter += 1
        rec = AnalysisRecord(
            step=self._step_counter,
            analysis_type=analysis_type,
            findings=findings[:1000],
            evolution_suggestions=evolution_suggestions or [],
        )
        self._write_line({"type": "analysis", **asdict(rec)})
        return self._step_counter

    def close(self) -> Dict[str, Any]:
        """Finalize recording, return summary stats."""
        elapsed = time.monotonic() - self._start_time
        summary = {
            "type": "session_end",
            "session_id": self._session_id,
            "total_steps": self._step_counter,
            "duration_seconds": round(elapsed, 2),
            "end_time": datetime.now(timezone.utc).isoformat(),
        }
        self._write_line(summary)
        return summary

    # ── Internals ───────────────────────────────────────────────────────

    def _write_line(self, obj: Dict[str, Any]) -> None:
        """Append one JSON line. Atomic: write then flush."""
        with open(self._file_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(obj, ensure_ascii=False) + "\n")
            f.flush()
            os.fsync(f.fileno())

    @property
    def file_path(self) -> Path:
        return self._file_path


# ── Post-hoc utilities ──────────────────────────────────────────────────────

def extract_errors(file_path: Path) -> List[Dict[str, Any]]:
    """Extract all failed tool calls from a trajectory JSONL."""
    errors = []
    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            rec = json.loads(line)
            if rec.get("type") == "tool_call" and not rec.get("success", True):
                errors.append(rec)
    return errors


def generate_summary(file_path: Path) -> Dict[str, Any]:
    """Generate execution summary from a trajectory JSONL."""
    tool_calls = 0
    failures = 0
    agent_actions = 0
    analyses = 0
    total_duration_ms = 0.0
    tools_used: Dict[str, int] = {}

    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            rec = json.loads(line)
            t = rec.get("type", "")
            if t == "tool_call":
                tool_calls += 1
                name = rec.get("tool_name", "unknown")
                tools_used[name] = tools_used.get(name, 0) + 1
                total_duration_ms += rec.get("duration_ms", 0)
                if not rec.get("success", True):
                    failures += 1
            elif t == "agent_action":
                agent_actions += 1
            elif t == "analysis":
                analyses += 1

    return {
        "tool_calls": tool_calls,
        "failures": failures,
        "failure_rate": round(failures / max(tool_calls, 1), 3),
        "agent_actions": agent_actions,
        "analyses": analyses,
        "total_duration_ms": total_duration_ms,
        "tools_used": tools_used,
    }
