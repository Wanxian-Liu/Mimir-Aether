"""Horizon C Wave 14 · P3-XSR-01 contract (doc-only grain)."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PROPOSAL = ROOT / "docs" / "proposals" / "p3-cross-session-retrieval.md"
TIER0 = ROOT / "run_ralph_tier0.sh"
CLOSEOUT = ROOT / "docs" / "phase0" / "p3-xsr-01-closeout.md"
HERMES = ROOT / "docs" / "hermes-comparison-detailed.md"
ADR_SPIKE = ROOT / "docs" / "phase0" / "adr-002-write-spike.md"


def test_p3_xsr_01_proposal_three_layers():
    text = PROPOSAL.read_text(encoding="utf-8")
    assert "L1" in text and "核心全量" in text
    assert "L2" in text and "Top-N" in text
    assert "L3" in text and "RAG" in text
    assert "_build_cross_session_context" in text


def test_p3_xsr_01_hermes_comparison_section():
    text = PROPOSAL.read_text(encoding="utf-8")
    assert "hermes-comparison-detailed" in text
    assert "Hermes" in text
    assert HERMES.is_file()


def test_p3_xsr_01_adr_002_gate_section():
    text = PROPOSAL.read_text(encoding="utf-8")
    assert "ADR-002" in text
    assert "G-ADR-002" in text
    assert "SESSION_SEARCH_BACKEND" in text
    assert "生产默认" in text or "production" in text.lower()
    assert ADR_SPIKE.is_file()


def test_p3_xsr_01_in_tier0():
    tier0 = TIER0.read_text(encoding="utf-8")
    assert "test_horizon_p3_xsr_01.py" in tier0


def test_p3_xsr_01_closeout_exists():
    assert CLOSEOUT.is_file()
