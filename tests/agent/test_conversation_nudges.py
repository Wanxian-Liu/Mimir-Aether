"""IQ-EVO-08: in-loop memory/skill nudges."""

from __future__ import annotations

from agent.conversation_nudges import (
    MEMORY_NUDGE_MARKER,
    SKILL_NUDGE_MARKER,
    maybe_memory_nudge_message,
    maybe_skill_nudge_message,
)


def test_memory_nudge_every_tenth_turn(monkeypatch):
    monkeypatch.setenv("MIMIR_MEMORY_NUDGE_INTERVAL", "10")
    assert maybe_memory_nudge_message(0) is None
    assert maybe_memory_nudge_message(9) and MEMORY_NUDGE_MARKER in maybe_memory_nudge_message(9)


def test_skill_nudge_requires_tool_calls(monkeypatch):
    monkeypatch.setenv("MIMIR_SKILL_NUDGE_INTERVAL", "5")
    monkeypatch.setenv("MIMIR_SKILL_NUDGE_MIN_TOOLS", "3")
    assert maybe_skill_nudge_message(4, tool_calls_so_far=2) is None
    msg = maybe_skill_nudge_message(4, tool_calls_so_far=5)
    assert msg and SKILL_NUDGE_MARKER in msg


def test_nudge_interval_zero_disables(monkeypatch):
    monkeypatch.setenv("MIMIR_MEMORY_NUDGE_INTERVAL", "0")
    monkeypatch.setenv("MIMIR_SKILL_NUDGE_INTERVAL", "0")
    assert maybe_memory_nudge_message(9) is None
    assert maybe_skill_nudge_message(9, tool_calls_so_far=99) is None
