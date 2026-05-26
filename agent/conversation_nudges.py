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


__all__ = [
    "MEMORY_NUDGE_MARKER",
    "SKILL_NUDGE_MARKER",
    "maybe_memory_nudge_message",
    "maybe_skill_nudge_message",
]
