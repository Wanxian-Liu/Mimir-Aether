"""Tests for turn_loop_utils — ENG-WF-21."""

from __future__ import annotations

from agent.turn_loop import Turn, TurnStatus
from agent.turn_loop_utils import compute_turn_statistics


def test_compute_empty_list():
    """Empty turn list → success_rate=0.0, all zeros."""
    stats = compute_turn_statistics([])
    assert stats["total_turns"] == 0
    assert stats["completed"] == 0
    assert stats["failed"] == 0
    assert stats["success_rate"] == 0.0


def test_compute_mixed_statuses():
    """Mixed completed/failed/running turns → correct counts."""
    turns = [
        Turn(id="t1", user_message="hi", status=TurnStatus.COMPLETED, iterations=3),
        Turn(id="t2", user_message="hello", status=TurnStatus.COMPLETED, iterations=5),
        Turn(id="t3", user_message="hey", status=TurnStatus.FAILED),
        Turn(id="t4", user_message="ho", status=TurnStatus.RUNNING),
    ]
    stats = compute_turn_statistics(turns)
    assert stats["total_turns"] == 4
    assert stats["completed"] == 2
    assert stats["failed"] == 1
    assert stats["running"] == 1
    assert stats["success_rate"] == 0.5
    assert stats["total_iterations"] == 8


def test_compute_all_max_iterations():
    """All turns maxed out → success_rate=0.0."""
    turns = [
        Turn(id="t1", user_message="x", status=TurnStatus.MAX_ITERATIONS),
        Turn(id="t2", user_message="y", status=TurnStatus.MAX_ITERATIONS),
    ]
    stats = compute_turn_statistics(turns)
    assert stats["total_turns"] == 2
    assert stats["completed"] == 0
    assert stats["max_iterations"] == 2
    assert stats["success_rate"] == 0.0
