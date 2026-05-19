"""
Conversation formatter for post-execution analysis.

Learned from OpenSpace skill_engine/conversation_formatter.py:
  - Priority-based truncation (0=critical, 5=low)
  - Error detection in tool results
  - Embedded summary extraction
  - Tool calls + errors paired together

Converts MimirAether execution trajectory (JSONL) into a structured text
block for LLM analysis prompts.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional


# Per-section truncation limits
TOOL_ERROR_MAX_CHARS = 1000
TOOL_SUCCESS_MAX_CHARS = 800
TOOL_ARGS_MAX_CHARS = 500
TOOL_SUMMARY_MAX_CHARS = 1500


def format_trajectory_for_analysis(
    trajectory_path: str,
    budget: int = 50_000,
) -> str:
    """Format a trajectory JSONL into analysis-ready text.

    Priority levels:
      0 — CRITICAL : User task description (never truncated)
      1 — CRITICAL : Final tool results
      2 — HIGH     : Tool errors
      3 — HIGH     : Tool calls (name + args)
      4 — MEDIUM   : Tool success results
      5 — LOW      : Agent actions / metadata
    """
    if not trajectory_path or not Path(trajectory_path).exists():
        return ""

    with open(trajectory_path, "r", encoding="utf-8") as f:
        lines = [json.loads(line) for line in f if line.strip()]

    segments: List[Dict[str, Any]] = []
    tool_errors: List[Dict] = []

    for entry in lines:
        t = entry.get("type", "")

        if t == "session_start":
            task = entry.get("task_name", "unnamed")
            segments.append({
                "priority": 0,
                "text": f"[TASK] {task}\nSession: {entry.get('session_id', '')}\nStarted: {entry.get('start_time', '')}",
            })

        elif t == "tool_call":
            name = entry.get("tool_name", "?")
            args = _format_args(entry.get("arguments", {}))
            success = entry.get("success", True)
            error = entry.get("error_message", "")
            result = entry.get("result_summary", "")
            duration = entry.get("duration_ms", 0)

            # Tool call header
            call_text = f"[TOOL] {name}({args})"
            if duration:
                call_text += f" [{duration:.0f}ms]"
            segments.append({
                "priority": 3,
                "text": call_text,
            })

            # Result
            if not success:
                err_text = f"[ERROR] {name}: {error[:TOOL_ERROR_MAX_CHARS]}"
                if result:
                    err_text += f"\n  Result: {result[:TOOL_SUCCESS_MAX_CHARS]}"
                segments.append({
                    "priority": 2,
                    "text": err_text,
                })
                tool_errors.append(entry)
            else:
                summary = _extract_summary(result) or result
                segments.append({
                    "priority": 4,
                    "text": f"  OK: {summary[:TOOL_SUCCESS_MAX_CHARS]}",
                })

        elif t == "agent_action":
            atype = entry.get("action_type", "")
            summary = entry.get("summary", "")[:TOOL_SUMMARY_MAX_CHARS]
            segments.append({
                "priority": 5,
                "text": f"[ACTION] {atype}: {summary}",
            })

        elif t == "analysis":
            findings = entry.get("findings", "")[:TOOL_SUMMARY_MAX_CHARS]
            segments.append({
                "priority": 3,
                "text": f"[ANALYSIS] {findings}",
            })

    # Assemble with budget
    return _assemble(segments, budget, tool_errors)


def _format_args(args: Dict[str, Any]) -> str:
    """Format tool arguments compactly."""
    if not args:
        return ""
    parts = []
    for k, v in args.items():
        vs = str(v)
        if len(vs) > TOOL_ARGS_MAX_CHARS:
            vs = vs[:TOOL_ARGS_MAX_CHARS] + "..."
        parts.append(f"{k}={vs}")
    return ", ".join(parts)


def _extract_summary(content: str) -> Optional[str]:
    """Extract self-generated summary from tool result."""
    if not content:
        return None
    # Look for summary markers
    match = re.search(
        r"(?:Summary|Result|Output)[:\s]+(.+?)(?:\n\n|\n[A-Z]|$)",
        content, re.DOTALL | re.IGNORECASE,
    )
    if match:
        summary = match.group(1).strip()
        if len(summary) > 10:
            return summary[:TOOL_SUMMARY_MAX_CHARS]
    return content[:TOOL_SUCCESS_MAX_CHARS] if len(content) > TOOL_SUCCESS_MAX_CHARS else content


def _is_error(content: str) -> bool:
    """Detect error patterns in tool result."""
    if not content:
        return False
    head = content[:200].lower()
    return any([
        content.startswith("[ERROR]"),
        "error" in head[:50],
        "task failed" in head,
        "traceback" in head,
        "timed out" in head,
        "connection refused" in head,
    ])


def _assemble(
    segments: List[Dict[str, Any]],
    budget: int,
    tool_errors: List[Dict],
) -> str:
    """Assemble segments with priority-based budget management."""
    # Sort by priority (0 first), preserve original order within priority
    indexed = list(enumerate(segments))
    indexed.sort(key=lambda x: (x[1]["priority"], x[0]))

    output: List[str] = []
    used = 0

    # Pass 1: priority 0-2 (CRITICAL + HIGH errors) — keep in full
    for _, seg in indexed:
        if seg["priority"] > 2:
            break
        text = seg["text"]
        if used + len(text) + 1 <= budget:
            output.append(text)
            used += len(text) + 1

    remaining = budget - used

    # Pass 2: priority 3 (tool calls) — budget-allocated
    p3 = [s for _, s in indexed if s["priority"] == 3]
    if p3 and remaining > 0:
        per_item = max(200, remaining // (len(p3) + 1))
        kept = 0
        for seg in p3:
            text = seg["text"][:per_item] + ("..." if len(seg["text"]) > per_item else "")
            if used + len(text) + 1 <= budget:
                output.append(text)
                used += len(text) + 1
                kept += 1
        if kept < len(p3):
            output.append(f"[... {len(p3) - kept} more tool calls omitted ...]")

    remaining = budget - used

    # Pass 3: priority 4-5 (success results, actions) — one-line summaries
    p45 = [(i, s) for i, s in indexed if s["priority"] >= 4]
    if p45 and remaining > 200:
        output.append("\n--- Tool results summary ---")
        lines = 0
        for _, seg in p45:
            first_line = seg["text"].split("\n", 1)[0][:200]
            if used + len(first_line) + 1 > budget or lines > 20:
                output.append("[... remaining results omitted ...]")
                break
            output.append(first_line)
            used += len(first_line) + 1
            lines += 1

    # Error summary
    if tool_errors:
        error_names = set(e.get("tool_name", "?") for e in tool_errors)
        output.append(f"\n[ERROR SUMMARY] {len(tool_errors)} errors in tools: {', '.join(error_names)}")

    return "\n".join(output)
