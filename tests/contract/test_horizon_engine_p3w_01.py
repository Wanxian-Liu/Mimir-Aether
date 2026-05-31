"""Horizon C · ENGINE-P3W-01 contract (ADR-002 MemoryWriteFacade)."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FACADE = ROOT / "agent" / "memory_write_facade.py"
CROSS = ROOT / "agent" / "cross_session_memory.py"
CURATOR = ROOT / "agent" / "skill_curator.py"
MIMIRCORE = ROOT / "tools" / "mimircore_tool.py"
TIER0 = ROOT / "run_ralph_tier0.sh"
CLOSEOUT = ROOT / "docs" / "phase0" / "engine-p3w-01-closeout.md"
GATE = ROOT / "docs" / "phase0" / "adr-002-impl-gate-brief.md"


def test_engine_p3w_01_facade_api():
    text = FACADE.read_text(encoding="utf-8")
    assert "ENGINE-P3W-01" in text or "ADR-002" in text
    assert "write_capsule_html" in text
    assert "write_persistent_mutator" in text
    assert "save_persistent_merged" in text


def test_engine_p3w_01_call_sites_wired():
    assert "save_persistent_merged" in CROSS.read_text(encoding="utf-8")
    curator = CURATOR.read_text(encoding="utf-8")
    assert "memory_write_facade" in curator
    assert "persistent_store.read_modify_write" not in curator
    mimir = MIMIRCORE.read_text(encoding="utf-8")
    assert "write_capsule_html" in mimir
    assert "memory_write_facade" in mimir


def test_engine_p3w_01_docs_and_tier0():
    assert CLOSEOUT.is_file()
    assert GATE.is_file()
    tier0 = TIER0.read_text(encoding="utf-8")
    assert "test_memory_write_facade_p3w.py" in tier0
    assert "test_horizon_engine_p3w_01.py" in tier0
