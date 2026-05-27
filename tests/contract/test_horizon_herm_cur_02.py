"""Horizon C Wave 10 · HERM-CUR-02 contract."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CURATOR = ROOT / "agent/skill_curator.py"
TIER0 = ROOT / "run_ralph_tier0.sh"
CLOSEOUT = ROOT / "docs/phase0/herm-cur-02-closeout.md"


def test_herm_cur_02_lifecycle_exports():
    text = CURATOR.read_text(encoding="utf-8")
    for symbol in (
        "scan_all_skills",
        "run_lifecycle_pass",
        "schedule_skill_curator_lifecycle_pass",
        "MIMIR_SKILL_CURATOR_ON_CLOSE",
    ):
        assert symbol in text


def test_herm_cur_02_close_hook_in_agent_loop():
    loop = (ROOT / "agent/agent_loop.py").read_text(encoding="utf-8")
    assert "schedule_skill_curator_lifecycle_pass" in loop


def test_herm_cur_02_in_tier0():
    tier0 = TIER0.read_text(encoding="utf-8")
    assert "test_skill_curator_lifecycle.py" in tier0
    assert "test_horizon_herm_cur_02.py" in tier0


def test_herm_cur_02_closeout_exists():
    assert CLOSEOUT.is_file()
