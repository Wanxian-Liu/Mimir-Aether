"""Horizon C Wave 15 · P3-XSR-02 contract (L2 prefetch)."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MODULE = ROOT / "agent" / "cross_session_retrieval.py"
PROMPT = ROOT / "agent" / "prompt_builder.py"
GATEWAY = ROOT / "gateway" / "agent_mixin.py"
SESSION_CMD = ROOT / "gateway" / "router" / "session_commands_mixin.py"
TIER0 = ROOT / "run_ralph_tier0.sh"
CLOSEOUT = ROOT / "docs" / "phase0" / "p3-xsr-02-closeout.md"
TESTS = ROOT / "tests" / "agent" / "test_cross_session_retrieval_l2.py"


def test_p3_xsr_02_l2_module_and_env():
    text = MODULE.read_text(encoding="utf-8")
    assert "MIMIR_CROSS_SESSION_RETRIEVAL" in text
    assert "MIMIR_CROSS_SESSION_RETRIEVAL_MAX_CHARS" in text
    assert "derive_retrieval_query" in text
    assert "<retrieved-sessions>" in text
    assert "session_search" in text


def test_p3_xsr_02_prompt_builder_wired():
    text = PROMPT.read_text(encoding="utf-8")
    assert "build_retrieved_sessions_context" in text


def test_p3_xsr_02_gateway_prefetch_queue():
    assert "request_cross_session_prefetch" in GATEWAY.read_text(encoding="utf-8")
    assert "request_cross_session_prefetch" in SESSION_CMD.read_text(encoding="utf-8")


def test_p3_xsr_02_in_tier0():
    tier0 = TIER0.read_text(encoding="utf-8")
    assert "test_horizon_p3_xsr_02.py" in tier0
    assert "test_cross_session_retrieval_l2.py" in tier0


def test_p3_xsr_02_closeout_exists():
    assert CLOSEOUT.is_file()
    assert TESTS.is_file()
