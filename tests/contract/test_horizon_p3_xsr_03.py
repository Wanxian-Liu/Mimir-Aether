"""Horizon C · P3-XSR-03 contract (L3 RAG flag, merged with L2)."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODULE = ROOT / "agent" / "cross_session_retrieval.py"
TOOL = ROOT / "tools" / "session_search_tool.py"
TIER0 = ROOT / "run_ralph_tier0.sh"
CLOSEOUT = ROOT / "docs" / "phase0" / "p3-xsr-03-closeout.md"
TESTS = ROOT / "tests" / "agent" / "test_cross_session_retrieval_l3.py"


def test_p3_xsr_03_rag_flag_default_off():
    text = MODULE.read_text(encoding="utf-8")
    assert "cross_session_rag_enabled" in text
    assert 'get("MIMIR_CROSS_SESSION_RAG", "0")' in text


def test_p3_xsr_03_session_search_prefetch_api():
    text = TOOL.read_text(encoding="utf-8")
    assert "def session_search_prefetch" in text
    assert "use_rag" in text
    assert "_session_search_via_fusion" in text


def test_p3_xsr_03_merged_injection_block():
    text = MODULE.read_text(encoding="utf-8")
    assert "run_prefetch_search" in text
    assert "<retrieved-sessions>" in text
    assert "session_search_prefetch" in text


def test_p3_xsr_03_does_not_change_backend_default():
    text = TOOL.read_text(encoding="utf-8")
    assert '_DEFAULT_SESSION_SEARCH_BACKEND = "hybrid"' in text


def test_p3_xsr_03_in_tier0():
    tier0 = TIER0.read_text(encoding="utf-8")
    assert "test_horizon_p3_xsr_03.py" in tier0
    assert "test_cross_session_retrieval_l3.py" in tier0


def test_p3_xsr_03_closeout_exists():
    assert CLOSEOUT.is_file()
    assert TESTS.is_file()
