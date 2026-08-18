"""In-loop memory/skill nudges (IQ-EVO-08 · Hermes-style intervals)."""

from __future__ import annotations

import os
from typing import Optional

MEMORY_NUDGE_MARKER = "[MIMIR_MEMORY_NUDGE]"
SKILL_NUDGE_MARKER = "[MIMIR_SKILL_NUDGE]"

_MEMORY_NUDGE_TEXT = (
    f"{MEMORY_NUDGE_MARKER} Before finishing: if anything durable should survive "
    "this session, save it with the memory tool (preferences, env quirks, "
    "conventions). For past work, use session_search — do not ask the user to "
    "repeat history you can retrieve."
)

_SKILL_NUDGE_TEXT = (
    f"{SKILL_NUDGE_MARKER} If this thread uncovered a repeatable workflow (several "
    "tool calls, error recovery, or a non-obvious fix), capture or update a skill "
    "with skill_manage per SOUL growth rules."
)


def _nudge_interval(env_name: str, default: int) -> int:
    raw = os.environ.get(env_name, str(default)).strip()
    try:
        value = int(raw)
    except ValueError:
        value = default
    return max(0, value)


def maybe_memory_nudge_message(turn: int) -> Optional[str]:
    """Return a user nudge every N turns (0-based turn index)."""
    interval = _nudge_interval("MIMIR_MEMORY_NUDGE_INTERVAL", 10)
    if interval == 0 or turn <= 0 or (turn + 1) % interval != 0:
        return None
    return _MEMORY_NUDGE_TEXT


def maybe_skill_nudge_message(turn: int, tool_calls_so_far: int) -> Optional[str]:
    """Return a skill nudge when enough tools ran to justify capture."""
    interval = _nudge_interval("MIMIR_SKILL_NUDGE_INTERVAL", 10)
    min_tools = _nudge_interval("MIMIR_SKILL_NUDGE_MIN_TOOLS", 3)
    if interval == 0 or turn <= 0 or (turn + 1) % interval != 0:
        return None
    if tool_calls_so_far < min_tools:
        return None
    return _SKILL_NUDGE_TEXT


PARALLEL_READ_NUDGE_MARKER = "[MIMIR_PARALLEL_READ_NUDGE]"

_PARALLEL_READ_NUDGE_TEXT = (
    f"{PARALLEL_READ_NUDGE_MARKER} 当前任务已连续多轮调用工具。"
    "若本轮仍需只读查询（search_files / read_file / terminal 的 grep/stat 类），"
    "请一次返回 ≥2 个只读 tool_calls 并行执行（模型并行工具调用）——"
    "写工具（write_file / patch / terminal 写操作）保持串行。"
    "并行只读 = 每轮省 1 次 API 往返（~20s）。"
)


def maybe_parallel_read_nudge(turn: int, tool_calls_so_far: int) -> Optional[str]:
    """P0-4 (2026-08-19)：turn≥3 且已有多轮工具调用时，注入"并行只读"提示。

    架构钩子（非 AGENTS.md 静态纪律）：运行时注入——模型可拒绝，但显式提示如何并行。
    env 开关 MIMIR_PARALLEL_READ_NUDGE（默认 1=开，0=关回退）。
    """
    enabled = os.environ.get("MIMIR_PARALLEL_READ_NUDGE", "1").strip().lower()
    if enabled in ("0", "false", "no", "off"):
        return None
    # turn 是 0-based；turn >= 3 即第 4 轮起（执行卡：turn≥3 注入）
    if turn < 3:
        return None
    # 至少 2 次工具调用后才提示（防首轮打扰）
    if tool_calls_so_far < 2:
        return None
    return _PARALLEL_READ_NUDGE_TEXT


__all__ = [
    "MEMORY_NUDGE_MARKER",
    "SKILL_NUDGE_MARKER",
    "maybe_memory_nudge_message",
    "maybe_skill_nudge_message",
    "PARALLEL_READ_NUDGE_MARKER",
    "maybe_parallel_read_nudge",
]
