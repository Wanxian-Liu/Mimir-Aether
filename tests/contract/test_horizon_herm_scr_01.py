"""Horizon C Wave 12 · HERM-SCR-01 contract."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRUBBER = ROOT / "agent/think_scrubber.py"
CALLERS = ROOT / "agent/callers_mixin.py"
TIER0 = ROOT / "run_ralph_tier0.sh"
CLOSEOUT = ROOT / "docs/phase0/herm-scr-01-closeout.md"


def test_herm_scr_01_scrubber_module():
    text = SCRUBBER.read_text(encoding="utf-8")
    for symbol in ("StreamingThinkScrubber", "strip_think_blocks", "redacted_thinking"):
        assert symbol in text


def test_herm_scr_01_stream_wiring():
    callers = CALLERS.read_text(encoding="utf-8")
    assert "StreamingThinkScrubber" in callers
    assert "flush()" in callers


def test_herm_scr_01_in_tier0():
    tier0 = TIER0.read_text(encoding="utf-8")
    assert "test_think_scrubber.py" in tier0
    assert "test_horizon_herm_scr_01.py" in tier0


def test_herm_scr_01_closeout_exists():
    assert CLOSEOUT.is_file()
