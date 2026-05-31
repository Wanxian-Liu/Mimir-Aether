"""Horizon C Wave 15+ · ENGINE-ROLLBACK-01 contract (STAB-05 evidence)."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ROLLBACK = ROOT / "agent" / "evolution_rollback.py"
SKILL_EVOLUTION = ROOT / "agent" / "skill_evolution.py"
TIER0 = ROOT / "run_ralph_tier0.sh"
CLOSEOUT = ROOT / "docs" / "phase0" / "engine-rollback-01-closeout.md"
STAB_BACKLOG = ROOT / "docs" / "GATEWAY_STABILITY_BACKLOG.md"
OPS = ROOT / "docs" / "OPERATIONS_GATEWAY.md"
STAB05_TEST = ROOT / "tests" / "agent" / "test_evolution_rollback_stab05.py"


def test_engine_rollback_01_module_and_backup_path():
    text = ROLLBACK.read_text(encoding="utf-8")
    assert "STAB-05" in text
    assert "save_skill_evolution_backup" in text
    assert "write_skill_md_guarded" in text
    assert "create_skill_dir_guarded" in text
    assert "evolution_backups" in text
    assert "skills_guard" in text


def test_engine_rollback_01_skill_evolution_wired():
    text = SKILL_EVOLUTION.read_text(encoding="utf-8")
    assert "evolution_rollback" in text
    assert "write_skill_md_guarded" in text
    assert "create_skill_dir_guarded" in text


def test_engine_rollback_01_stab_backlog_and_ops():
    assert "STAB-05" in STAB_BACKLOG.read_text(encoding="utf-8")
    ops = OPS.read_text(encoding="utf-8")
    assert "STAB-05" in ops or "自修回滚" in ops
    assert "evolution_backups" in ops


def test_engine_rollback_01_tests_in_tier0():
    tier0 = TIER0.read_text(encoding="utf-8")
    assert "test_evolution_rollback_stab05.py" in tier0
    assert "test_horizon_engine_rollback_01.py" in tier0


def test_engine_rollback_01_closeout_exists():
    assert CLOSEOUT.is_file()
    assert STAB05_TEST.is_file()
