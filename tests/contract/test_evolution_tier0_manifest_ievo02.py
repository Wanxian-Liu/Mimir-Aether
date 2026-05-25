"""IEVO-02 / D5-3: evolution-path pytest files must stay on the tier0 manifest."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TIER0 = ROOT / "run_ralph_tier0.sh"

# Production evolution stack covered by Gate2 (keep in sync with run_ralph_tier0.sh).
EVOLUTION_TIER0_PATHS = (
    "agent/test_skill_evolution.py",
    "agent/test_self_evolution_jepa.py",
    "tests/agent/test_skill_evolution_smoke.py",
    "tests/agent/test_self_evolution_smoke.py",
    "tests/agent/test_e007_evolution_security.py",
    "tests/agent/test_skill_evolution_e009.py",
    "tests/agent/test_evolution_loop_integration.py",
    "tests/agent/test_evolution_rollback_stab05.py",
    "tests/contract/test_no_simulated_evolution_ievo01.py",
)


def test_evolution_paths_listed_in_run_ralph_tier0():
    text = TIER0.read_text(encoding="utf-8")
    missing = [p for p in EVOLUTION_TIER0_PATHS if p not in text]
    assert not missing, "add to run_ralph_tier0.sh:\n" + "\n".join(missing)
