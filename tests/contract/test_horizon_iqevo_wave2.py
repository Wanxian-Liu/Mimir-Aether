"""Horizon Wave 2 (IQ-EVO-07～09) contract."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TIER0 = ROOT / "run_ralph_tier0.sh"
BACKLOG = ROOT / "docs/MIMIR_EXEC_BACKLOG.md"
AGENT_LOOP = ROOT / "agent/agent_loop.py"
PROMPT_BUILDER = ROOT / "agent/prompt_builder.py"

WAVE2_IDS = (
    "IQ-EVO-07",
    "IQ-EVO-08",
    "IQ-EVO-09",
)


def test_wave2_modules_wired():
    assert (ROOT / "agent/post_close_analysis.py").is_file()
    assert (ROOT / "agent/conversation_nudges.py").is_file()
    loop = AGENT_LOOP.read_text(encoding="utf-8")
    assert "schedule_post_close_analysis" in loop
    assert "maybe_memory_nudge_message" in loop
    pb = PROMPT_BUILDER.read_text(encoding="utf-8")
    assert "_cross_session_max_chars" in pb
    assert "current_objective" in pb


def test_backlog_wave2_items_present():
    text = BACKLOG.read_text(encoding="utf-8")
    assert "Wave 2" in text
    for item in WAVE2_IDS:
        assert f"**{item}**" in text


def test_wave2_tests_listed_in_tier0():
    text = TIER0.read_text(encoding="utf-8")
    assert "tests/agent/test_post_close_analysis.py" in text
    assert "tests/agent/test_conversation_nudges.py" in text
    assert "tests/contract/test_horizon_iqevo_wave2.py" in text
