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
import re
import time
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


def _get_trajectory_dir() -> Path:
    """Resolve trajectory storage directory (ADR-005 SoT under runtime data home)."""
    from mimir_constants import get_mimir_data_dir

    return get_mimir_data_dir() / "trajectories"


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

    def close(self, exit_reason: str = "", final_response_summary: str = "", task_spec: str = "") -> Dict[str, Any]:
        """Finalize recording, return summary stats.

        B7 (2026-08-29): session_end 追加 exit_reason + final_response_summary
        （FR-008 可回溯性——静默零产出从轨迹一行判定）。

        修复B（2026-08-30 self-fix）：session_end 自动落盘进度——task_name + 完成状态 +
        未完成 [ ] 项追加写入 ~/.mimiraether/PROGRESS.md（治跨 run 记忆断裂）。
        """
        elapsed = time.monotonic() - self._start_time
        summary = {
            "type": "session_end",
            "session_id": self._session_id,
            "total_steps": self._step_counter,
            "duration_seconds": round(elapsed, 2),
            "end_time": datetime.now(timezone.utc).isoformat(),
            "exit_reason": exit_reason,
            "final_response_summary": final_response_summary[:500],
        }
        self._write_line(summary)
        self._append_progress_md(exit_reason=exit_reason, task_spec=task_spec)
        return summary

    def _append_progress_md(self, exit_reason: str, task_spec: str) -> None:
        """修复B（2026-08-30 self-fix）：进度落盘——追加式（不覆盖、不幂等去重）。

        每次 run 结束追加一节：UTC 时间 + run(task_name) + 完成状态 + 未完成 [ ] 项。
        完成状态判定：exit_reason == "natural" 且无未完成 [ ] 项 → completed，否则 incomplete。
        """
        try:
            _home = Path(os.path.expanduser("~/.mimiraether"))
            _progress = _home / "PROGRESS.md"
            _now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
            # 提取未完成 [ ] 项（与 task_completion._CHECKBOX_RE 同款）
            _unfinished = []
            if task_spec:
                for _m in re.finditer(r"^-\s+\[([ xX])\]\s*(.+)$", task_spec, re.MULTILINE):
                    if _m.group(1).lower() != "x":
                        _unfinished.append(_m.group(2).strip())
            _status = "completed" if (exit_reason == "natural" and not _unfinished) else "incomplete"
            with open(_progress, "a", encoding="utf-8") as f:
                f.write(f"\n## {_now} · run: {self._task_name} · session: {self._session_id}\n")
                f.write(f"- status: **{_status}** · exit_reason: `{exit_reason}`\n")
                if _unfinished:
                    f.write(f"- 未完成 [ ] 项（{len(_unfinished)}）:\n")
                    for _item in _unfinished:
                        f.write(f"  - [ ] {_item}\n")
                else:
                    f.write("- 未完成 [ ] 项：无\n")
        except Exception as _exc:
            # 进度落盘失败不阻断 close（best-effort——trajectory JSONL 仍是真源）
            print(f"[execution_recorder] _append_progress_md skipped: {_exc}")

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
