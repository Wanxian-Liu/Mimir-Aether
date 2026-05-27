"""Wave 8 IQ-EVO-49 grain B contract (tier0 manifest)."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TIER0 = ROOT / "run_ralph_tier0.sh"
BACKLOG = ROOT / "docs/MIMIR_EXEC_BACKLOG.md"
PROMPT_BUILDER = ROOT / "agent/prompt_builder.py"


def test_grain_b_helpers_in_prompt_builder():
    text = PROMPT_BUILDER.read_text(encoding="utf-8")
    assert "_append_recent_memory_rows" in text
    assert "key_decisions" in text
    assert "learned_patterns" in text
    assert "MIMIR_CROSS_SESSION_DECISIONS_MAX" in text
    assert "MIMIR_CROSS_SESSION_PATTERNS_MAX" in text


def test_backlog_iq_evo_49_present():
    text = BACKLOG.read_text(encoding="utf-8")
    assert "**IQ-EVO-49**" in text
    assert "粒 B" in text


def test_wave8_grain_b_tests_in_tier0():
    tier0 = TIER0.read_text(encoding="utf-8")
    assert "test_horizon_iqevo_wave8_grain_b.py" in tier0
    assert "test_cross_session_grain_b.py" in tier0
