"""OS-REV-01: automatic skill description quality review."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from agent.skill_description_reviewer import (
    build_description_review_report,
    format_description_review_section,
    load_description_review_report,
    review_discovered_skills,
    save_description_review_report,
    score_skill_description,
    skill_description_review_enabled,
)


def test_skill_description_review_default_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MIMIR_SKILL_DESCRIPTION_REVIEW", raising=False)
    assert skill_description_review_enabled()


def test_skill_description_review_env_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MIMIR_SKILL_DESCRIPTION_REVIEW", "0")
    assert not skill_description_review_enabled()


def test_score_missing_description() -> None:
    rev = score_skill_description("foo", "")
    assert rev.score == 0
    assert any("missing" in i.lower() for i in rev.issues)


def test_score_good_description() -> None:
    desc = (
        "Use when the user asks to refactor Python modules with tests. "
        "Covers pytest, type hints, and small diffs."
    )
    rev = score_skill_description("refactor-py", desc)
    assert rev.score >= 70
    assert rev.grade() in ("A", "B")


def test_score_too_short_description() -> None:
    rev = score_skill_description("x", "short desc")
    assert rev.score < 50
    assert any("short" in i.lower() for i in rev.issues)


def test_review_discovered_skills_and_persist(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MIMIR_AETHER_HOME", str(tmp_path))
    discovered = [
        ("good-skill", Path("/tmp/good"), {"name": "good-skill", "description": "Use when user needs deployment help on Vercel with env vars and preview URLs."}),
        ("bad-skill", Path("/tmp/bad"), {"name": "bad-skill", "description": ""}),
    ]
    report = review_discovered_skills(discovered)
    assert report["total"] == 2
    assert report["low_quality_count"] >= 1
    path = save_description_review_report(report)
    assert path.is_file()
    loaded = load_description_review_report()
    assert loaded["total"] == 2


def test_format_section_lists_worst() -> None:
    report = build_description_review_report(
        [
            score_skill_description("a", ""),
            score_skill_description(
                "b",
                "Use when user wants CI/CD pipeline setup with GitHub Actions and deploy gates.",
            ),
        ]
    )
    section = format_description_review_section(report)
    assert "Description quality" in section
    assert "a" in section
