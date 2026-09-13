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


# ── Run provenance (X2-a 同源) ──────────────────────────────────────────────

def _resolve_model_name() -> str:
    """当前模型名（坑三 F1 根治：session_start 自带 model）。

    与 ``last_context_usage.json`` **同源** —— ``context_usage_snapshot``
    的 ``_config_default_model()`` 读同一处 ``config.yaml`` 的 ``model.default``，
    使两条流可直接比对（验收判据：两值相等）。兜底 ``MIMIR_MODEL``；
    两条来源皆空时返回哨兵 ``"unknown"`` —— **不返回空串**（见下方注释）。

    Best-effort：任何异常都不阻断轨迹落盘。
    """
    value = ""
    try:
        from agent.context_usage_snapshot import _config_default_model
        value = str(_config_default_model() or "").strip()
    except Exception:  # pragma: no cover - 归因不得阻断记录
        value = ""
    if not value:
        value = (os.getenv("MIMIR_MODEL") or "").strip()
    # F1 判据是「session_start 自带**非空** model」：两条来源都取不到时写哨兵，
    # 不写空串。空串 = 字段在但无信息 ⇒ 归因链静默断掉（下游按 model join 时
    # 只会看到空白，无法区分「没记录」与「记录了但为空」）。2026-09-13 CI 实证：
    # 无 config.yaml 且无 MIMIR_MODEL 的 runner 上写 ''，而本地因进程内
    # MIMIR_MODEL 假绿 —— 与「字段在、信息不在」同型，故双修（产品 + 测试）。
    return value or "unknown"


def _trajectory_id_used(session_id: str) -> bool:
    """该 session_id 是否已在**任何日期目录**下被用作轨迹文件名（F4 判据）。"""
    if not session_id:
        return False
    try:
        root = _get_trajectory_dir()
        if not root.exists():
            return False
        for day in root.iterdir():
            if not day.is_dir():
                continue
            if (day / ("%s.jsonl" % session_id)).exists():
                return True
    except Exception:  # pragma: no cover
        return False
    return False


def _unique_session_id(base: str) -> str:
    """F4 根治：同一 id 已存在 ⇒ 追加短唯一后缀，保证 raw id 跨文件唯一。

    不变量：返回值的 ``<id>.jsonl`` 在任何日期目录中都不存在。
    """
    candidate = (base or "").strip() or uuid.uuid4().hex[:12]
    if not _trajectory_id_used(candidate):
        return candidate
    for _ in range(64):
        candidate = "%s-%s" % (base, uuid.uuid4().hex[:6])
        if not _trajectory_id_used(candidate):
            return candidate
    return "%s-%s" % (base, uuid.uuid4().hex[:12])


def _resolve_provenance() -> Dict[str, str]:
    """``trace_id`` / ``trigger_source`` / ``agent_id`` for the session_start line.

    Same provenance **source** as X2-a (``agent/run_context.py``), reached through
    whichever channel is actually available to this process:

    1. **in-process** — ``run_context.current_run()``. The gateway opens the run
       (``begin_run``) *before* the agent loop and the recorder is created inside
       that same run, so the context is directly visible (thread-local, plus
       ``run_context``'s own process-wide fallback for executor threads).
    2. **child process** — the X2-a env keys (``MIMIR_TRACE_ID`` /
       ``MIMIR_AGENT_ID``) plus ``MIMIR_TRIGGER_SOURCE``: a child spawned by a
       tool cannot see the parent's thread state, which is exactly why X2-a
       exports those keys. (``child_env_injection()`` is useless here - in a
       child, no run is open locally, so it returns ``{}``.)

    ``agent_id`` always resolves (``run_context.agent_id()`` defaults to
    ``"mimir"``). ``trace_id`` / ``trigger_source`` stay ``""`` when no run was
    ever opened (CLI / scripts / tests) - the same "no run => no provenance" rule
    ``child_env_injection()`` is locked to, so a session_start line never
    fabricates a join key that no other stream can match.

    Best-effort by design: provenance must never stop a trajectory being written.
    """
    trace_id = ""
    trigger_source = ""
    agent_id_value = ""

    # 1. in-process run context.
    try:
        from agent.run_context import agent_id as _rc_agent_id
        from agent.run_context import current_run as _rc_current_run
    except Exception:  # pragma: no cover - provenance must never break recording
        _rc_current_run = None
        _rc_agent_id = None

    if _rc_current_run is not None:
        try:
            ctx = _rc_current_run() or {}
        except Exception:  # pragma: no cover
            ctx = {}
        trace_id = str(ctx.get("trace_id") or "")
        trigger_source = str(ctx.get("trigger_source") or "")
        agent_id_value = str(ctx.get("agent_id") or "")

    if _rc_agent_id is not None and not agent_id_value:
        try:
            agent_id_value = str(_rc_agent_id() or "")
        except Exception:  # pragma: no cover
            pass

    # 2. X2-a env channel (keys injected into tool-spawned child processes).
    if not trace_id:
        trace_id = (os.getenv("MIMIR_TRACE_ID") or "").strip()
    if not trigger_source:
        trigger_source = (os.getenv("MIMIR_TRIGGER_SOURCE") or "").strip()
    if not agent_id_value:
        agent_id_value = (os.getenv("MIMIR_AGENT_ID") or "").strip()

    return {
        "trace_id": trace_id,
        "trigger_source": trigger_source,
        "agent_id": agent_id_value,
        "model": _resolve_model_name(),
    }


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
        # F4 根治（四方裁决 2026-09-13 · 窗口项 5）：调用方传入的 id 可能
        # 跨会话复用（agent_loop 传 self.task_id），导致同一 raw id 落在多个
        # 轨迹文件、HF 侧被当重复而静默丢弃。此处统一唯一化。
        self._session_id = _unique_session_id(
            session_id or uuid.uuid4().hex[:12]
        )
        self._step_counter = 0
        self._start_time = time.monotonic()
        self._start_ts = datetime.now(timezone.utc).isoformat()

        # Ensure directory
        _today_dir().mkdir(parents=True, exist_ok=True)

        self._file_path = _today_dir() / f"{self._session_id}.jsonl"

        # Fresh session file (avoid appending to stale trajectories on session reuse)
        # 坑三支持（Hermes 开工令 · X2-a 同源）: session_start 自带归因字段，
        # 使 HF v2 数据管线可直接消费每个会话文件，无需 join。
        _prov = _resolve_provenance()
        with open(self._file_path, "w", encoding="utf-8") as f:
            f.write(
                json.dumps(
                    {
                        "type": "session_start",
                        "session_id": self._session_id,
                        "task_name": self._task_name,
                        "start_time": self._start_ts,
                        "trace_id": _prov["trace_id"],
                        "trigger_source": _prov["trigger_source"],
                        "agent_id": _prov["agent_id"],
                        "model": _prov.get("model", ""),
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
