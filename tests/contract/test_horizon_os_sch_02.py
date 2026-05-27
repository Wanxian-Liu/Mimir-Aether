"""Horizon C Wave 11 · OS-SCH-02 contract."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "tools/session_search_tool.py"
TIER0 = ROOT / "run_ralph_tier0.sh"
CLOSEOUT = ROOT / "docs/phase0/os-sch-02-closeout.md"


def test_os_sch_02_fusion_exports():
    text = TOOL.read_text(encoding="utf-8")
    for symbol in (
        "rank_fusion_rrf",
        "session_search_fusion_enabled",
        "MIMIR_SESSION_SEARCH_FUSION",
        "_session_search_via_fusion",
    ):
        assert symbol in text


def test_os_sch_02_semantic_hybrid_uses_fusion_path():
    text = TOOL.read_text(encoding="utf-8")
    assert "session_search_fusion_enabled()" in text
    assert "_session_search_via_fusion" in text


def test_os_sch_02_in_tier0():
    tier0 = TIER0.read_text(encoding="utf-8")
    assert "test_session_search_fusion_rank.py" in tier0
    assert "test_horizon_os_sch_02.py" in tier0


def test_os_sch_02_closeout_exists():
    assert CLOSEOUT.is_file()
