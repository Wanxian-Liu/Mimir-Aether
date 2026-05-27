"""Horizon C Wave 10 · HERM-TGR-02 contract."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT / "agent/tool_call_cache.py"
TIER0 = ROOT / "run_ralph_tier0.sh"
CLOSEOUT = ROOT / "docs/phase0/herm-tgr-02-closeout.md"


def test_herm_tgr_02_metrics_exports():
    text = CACHE.read_text(encoding="utf-8")
    for symbol in ("get_stats", "reset_stats", "MIMIR_TOOL_CACHE_LOG"):
        assert symbol in text


def test_herm_tgr_02_in_tier0():
    tier0 = TIER0.read_text(encoding="utf-8")
    assert "test_tool_call_cache_metrics.py" in tier0
    assert "test_horizon_herm_tgr_02.py" in tier0


def test_herm_tgr_02_closeout_exists():
    assert CLOSEOUT.is_file()
