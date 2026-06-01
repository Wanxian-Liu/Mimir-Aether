"""Turn loop utility functions — pure, no side effects."""

from typing import Dict, List

from .turn_loop import Turn, TurnStatus


def compute_turn_statistics(turns: List[Turn]) -> Dict[str, object]:
    """Compute aggregate statistics from a list of Turns.

    Args:
        turns: List of Turn objects.

    Returns:
        Dict with total_turns, completed, failed, max_iterations,
        running, success_rate, total_iterations.
    """
    total = len(turns)
    completed = sum(1 for t in turns if t.status == TurnStatus.COMPLETED)
    failed = sum(1 for t in turns if t.status == TurnStatus.FAILED)
    max_iterations = sum(1 for t in turns if t.status == TurnStatus.MAX_ITERATIONS)
    running = sum(1 for t in turns if t.status == TurnStatus.RUNNING)

    return {
        "total_turns": total,
        "completed": completed,
        "failed": failed,
        "max_iterations": max_iterations,
        "running": running,
        "success_rate": completed / total if total > 0 else 0.0,
        "total_iterations": sum(t.iterations for t in turns if t.iterations > 0),
    }
