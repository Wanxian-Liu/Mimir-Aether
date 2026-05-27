"""Horizon C Wave 13 · OS-TOOL-SRCH-01 contract."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RANKER = ROOT / "agent" / "tool_ranker.py"
TOOL = ROOT / "tools" / "tool_search_tool.py"
MODEL_TOOLS = ROOT / "model_tools.py"
TOOLSETS = ROOT / "tools" / "toolsets.py"
TIER0 = ROOT / "run_ralph_tier0.sh"
CLOSEOUT = ROOT / "docs" / "phase0" / "os-tool-srch-01-closeout.md"


def test_os_tool_srch_01_ranker_exports():
    text = RANKER.read_text(encoding="utf-8")
    for symbol in (
        "ToolSearchEntry",
        "build_tool_search_index",
        "search_tools",
        "tool_search_enabled",
        "MIMIR_TOOL_SEARCH",
        "rank_fusion_rrf",
        "_ensure_tools_discovered",
    ):
        assert symbol in text


def test_os_tool_srch_01_registry_tool():
    text = TOOL.read_text(encoding="utf-8")
    assert 'name="tool_search"' in text
    assert "skills_list" in RANKER.read_text(encoding="utf-8") or "_iter_skill_entries" in RANKER.read_text(
        encoding="utf-8"
    )


def test_os_tool_srch_01_wired_in_discovery():
    assert "tools.tool_search_tool" in MODEL_TOOLS.read_text(encoding="utf-8")
    toolsets = TOOLSETS.read_text(encoding="utf-8")
    assert '"tool_search"' in toolsets


def test_os_tool_srch_01_in_tier0():
    tier0 = TIER0.read_text(encoding="utf-8")
    assert "test_tool_ranker.py" in tier0
    assert "test_horizon_os_tool_srch_01.py" in tier0


def test_os_tool_srch_01_closeout_exists():
    assert CLOSEOUT.is_file()
