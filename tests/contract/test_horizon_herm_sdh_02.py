"""Horizon C Wave 10 · HERM-SDH-02 contract."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PROMPT = ROOT / "agent/prompt_builder.py"
HINTS = ROOT / "agent/subdirectory_hints.py"
TIER0 = ROOT / "run_ralph_tier0.sh"
CLOSEOUT = ROOT / "docs/phase0/herm-sdh-02-closeout.md"


def test_herm_sdh_02_exports():
    text = HINTS.read_text(encoding="utf-8")
    for symbol in (
        "prompt_block",
        "build_subdirectory_hints_system_block",
        "MIMIR_SUBDIR_HINTS_IN_SYSTEM",
    ):
        assert symbol in text


def test_herm_sdh_02_wired_in_prompt_builder():
    pb = PROMPT.read_text(encoding="utf-8")
    assert "build_subdirectory_hints_system_block" in pb


def test_herm_sdh_02_in_tier0():
    tier0 = TIER0.read_text(encoding="utf-8")
    assert "test_subdirectory_hints_prompt.py" in tier0
    assert "test_horizon_herm_sdh_02.py" in tier0


def test_herm_sdh_02_closeout_exists():
    assert CLOSEOUT.is_file()
