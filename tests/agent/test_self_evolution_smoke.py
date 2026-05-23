"""
EP-C04 — self_evolution smoke tests (tests/agent/).

Three read-only / in-memory paths (no network, no file writes):
  1. EvolutionCost IC gate — safe file passes, core file blocked
  2. analyze() integration entry — structured audit result
  3. EvolutionMemory — should_retry after repeated failures
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent.self_evolution import EvolutionCost, EvolutionMemory, analyze
from agent.self_evolution.memory import EvolutionRecord


def test_self_evolution_ic_gate_safe_vs_core():
    cost = EvolutionCost()

    safe = cost.evaluate(["skill_evolution.py"], estimated_lines=10)
    blocked = cost.evaluate(["agent_loop.py"])

    assert safe.passed is True
    assert not safe.ic_violations
    assert blocked.passed is False
    assert blocked.ic_violations


def test_self_evolution_analyze_integration_smoke():
    result = analyze(
        ["skill_evolution.py", "tool_quality.py", "agent_loop.py"],
        force_refresh=False,
    )

    assert "passed" in result
    assert "violations" in result
    assert "safe_files" in result
    assert "plan" in result
    assert result["passed"] is False
    assert result["violations"]
    assert "skill_evolution.py" in result["safe_files"]


def test_self_evolution_memory_should_retry_smoke():
    mem = EvolutionMemory()
    for _ in range(3):
        mem.push(
            EvolutionRecord(
                timestamp=time.time(),
                changes=["broken.py"],
                ic_cost=0,
                tc_cost=1,
                total_cost=1,
                outcome="failed",
                tier0_result="FAIL",
            )
        )

    assert mem.should_retry("broken.py", max_failures=3) is False
    assert mem.should_retry("fresh.py", max_failures=3) is True
