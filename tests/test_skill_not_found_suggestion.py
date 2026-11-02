"""Regression gate for "Skill not found" nearest-name hints (2026-11-02).

Why: 42 of 75 historical ``skill_manage`` failures were ``Skill '<x>' not
found`` — a mistyped name, not a broken tool. The fix attaches nearest matches
so the caller can correct in one step. Two-way control is mandatory
(AGENTS §9 tier ④): a close name MUST get a hint, an unrelated name MUST NOT.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools import skill_manager_tool as smt


def _fake_skills(tmp_path):
    for name in ("alpha-skill", "beta-skill"):
        d = tmp_path / name
        d.mkdir()
        (d / "SKILL.md").write_text("---\nname: x\n---\n", encoding="utf-8")
    return tmp_path


def test_close_name_gets_suggestion(tmp_path, monkeypatch):
    root = _fake_skills(tmp_path)
    monkeypatch.setattr(smt, "_iter_skill_dirs", lambda: [root])

    message = smt.skill_not_found_error("alpha-skil")

    assert "not found" in message
    assert "Did you mean" in message
    assert "alpha-skill" in message


def test_unrelated_name_gets_no_suggestion(tmp_path, monkeypatch):
    root = _fake_skills(tmp_path)
    monkeypatch.setattr(smt, "_iter_skill_dirs", lambda: [root])

    message = smt.skill_not_found_error("zzz-nope-nonexistent-q")

    assert "not found" in message
    assert "Did you mean" not in message

# --- 活体路径回归（2026-11-02 审计 P1：原用例只覆盖 tools/ 侧，被注册遮蔽的那一份） ---

def test_live_loader_close_name_gets_hint():
    """LIVE entry = skills.skills_loader.skill_manage (agent/config_mixin.py:350).

    action=patch on a nonexistent name is read-only: it returns an error dict
    before touching any file, so this is safe to run on the real skills tree.
    """
    from skills.skills_loader import skill_manage

    result = skill_manage(action="patch", name="mimiraether-context-compresor",
                          old_string="x", new_string="y")
    payload = json.loads(result) if isinstance(result, str) else result

    assert payload.get("success") is False
    assert "Did you mean" in str(payload.get("error"))
    assert "mimiraether-context-compressor" in str(payload.get("error"))


def test_live_loader_unrelated_name_gets_no_hint():
    from skills.skills_loader import skill_manage

    result = skill_manage(action="patch", name="zzz-nope-nonexistent-q",
                          old_string="x", new_string="y")
    payload = json.loads(result) if isinstance(result, str) else result

    assert payload.get("success") is False
    assert "Did you mean" not in str(payload.get("error"))
