"""HERM-CUR-02: skill_curator lifecycle pass and on-close hook."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from agent.skill_curator import (
    SkillStatus,
    build_lifecycle_report,
    run_lifecycle_pass,
    scan_all_skills,
    schedule_skill_curator_lifecycle_pass,
)


def _write_skill(skill_dir, name: str) -> None:
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: test skill\n---\n\n# {name}\n",
        encoding="utf-8",
    )


def test_scan_marks_stale_after_threshold(tmp_path, monkeypatch):
    monkeypatch.setenv("MIMIR_AETHER_HOME", str(tmp_path))
    skills_root = tmp_path / "skills"
    _write_skill(skills_root / "general" / "stale-skill", "stale-skill")

    old = datetime.now(timezone.utc) - timedelta(days=35)
    monkeypatch.setattr(
        "agent.skill_curator._get_usage",
        lambda: {"stale-skill": old.isoformat()},
    )

    monkeypatch.setattr("agent.skill_curator.SKILLS_ROOT", skills_root)
    monkeypatch.setattr(
        "agent.skill_curator._collect_skill_roots", lambda: [skills_root]
    )

    rows = scan_all_skills()
    stale = [r for r in rows if r["status"] == SkillStatus.STALE]
    assert any(r["name"] == "stale-skill" for r in stale)


def test_run_lifecycle_pass_report_under_2kb(tmp_path, monkeypatch):
    monkeypatch.setenv("MIMIR_AETHER_HOME", str(tmp_path))
    skills_root = tmp_path / "skills"
    _write_skill(skills_root / "general" / "fresh-skill", "fresh-skill")

    monkeypatch.setattr("agent.skill_curator.SKILLS_ROOT", skills_root)
    monkeypatch.setattr(
        "agent.skill_curator._collect_skill_roots", lambda: [skills_root]
    )

    result = run_lifecycle_pass()
    assert result["total"] >= 1
    assert len(result["report_md"].encode("utf-8")) <= 2048


def test_schedule_skill_curator_on_close_spawns_when_env(monkeypatch):
    monkeypatch.setenv("MIMIR_SKILL_CURATOR_ON_CLOSE", "1")
    called = []

    monkeypatch.setattr(
        "agent.skill_curator.run_lifecycle_pass",
        lambda: called.append("ran") or {"total": 0, "report_md": ""},
    )

    schedule_skill_curator_lifecycle_pass(session_id="s1", task_name="t")
    import time

    time.sleep(0.2)
    assert called


def test_schedule_skill_curator_skips_when_env_off(monkeypatch):
    monkeypatch.delenv("MIMIR_SKILL_CURATOR_ON_CLOSE", raising=False)
    called = []

    monkeypatch.setattr(
        "agent.skill_curator.run_lifecycle_pass",
        lambda: called.append("ran"),
    )

    schedule_skill_curator_lifecycle_pass()
    import time

    time.sleep(0.15)
    assert not called


def test_build_lifecycle_report_truncates():
    skills = [{"name": f"s{i}", "status": "fresh"} for i in range(200)]
    buckets = {"fresh": skills, "stale": [], "dormant": []}
    actions = {
        "actions": [
            {
                "name": f"skill-{i}",
                "action": "review",
                "reason": "x" * 80,
            }
            for i in range(80)
        ],
        "summary": {},
    }
    text = build_lifecycle_report(skills, buckets, actions)
    assert len(text.encode("utf-8")) <= 2048
