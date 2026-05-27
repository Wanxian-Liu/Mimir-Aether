"""Horizon C Wave 12 · OS-REV-01 contract."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REVIEWER = ROOT / "agent" / "skill_description_reviewer.py"
CURATOR = ROOT / "agent" / "skill_curator.py"
SKILLS_QA = ROOT / "agent" / "skills_qa.py"
TIER0 = ROOT / "run_ralph_tier0.sh"
CLOSEOUT = ROOT / "docs" / "phase0" / "os-rev-01-closeout.md"


def test_os_rev_01_reviewer_module():
    text = REVIEWER.read_text(encoding="utf-8")
    for symbol in (
        "score_skill_description",
        "skill_description_review_enabled",
        "MIMIR_SKILL_DESCRIPTION_REVIEW",
        "run_description_review_pass",
        "save_description_review_report",
    ):
        assert symbol in text


def test_os_rev_01_uses_skills_qa_scoring_surface():
    assert "score_skill_quality" in SKILLS_QA.read_text(encoding="utf-8")


def test_os_rev_01_curator_lifecycle_hook():
    curator = CURATOR.read_text(encoding="utf-8")
    assert "skill_description_review_enabled" in curator
    assert "description_review" in curator


def test_os_rev_01_in_tier0():
    tier0 = TIER0.read_text(encoding="utf-8")
    assert "test_skill_description_reviewer.py" in tier0
    assert "test_horizon_os_rev_01.py" in tier0


def test_os_rev_01_closeout_exists():
    assert CLOSEOUT.is_file()
