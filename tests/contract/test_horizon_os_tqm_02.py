"""Horizon C Wave 11 · OS-TQM-02 contract."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
QUALITY = ROOT / "agent/tool_quality.py"
PROMPT = ROOT / "agent/prompt_builder.py"
REGISTRY = ROOT / "tools/registry.py"
SESSIONS = ROOT / "agent/execution_pipeline_sessions.py"
TIER0 = ROOT / "run_ralph_tier0.sh"
CLOSEOUT = ROOT / "docs/phase0/os-tqm-02-closeout.md"


def test_os_tqm_02_env_and_rank_exports():
    text = QUALITY.read_text(encoding="utf-8")
    for symbol in (
        "tool_quality_enabled",
        "MIMIR_TOOL_QUALITY",
        "order_tool_names_by_quality",
        "format_degraded_tools_guidance",
    ):
        assert symbol in text


def test_os_tqm_02_pipeline_and_registry_wired():
    assert "tool_quality_enabled" in SESSIONS.read_text(encoding="utf-8")
    assert "order_tool_names_by_quality" in REGISTRY.read_text(encoding="utf-8")
    assert "tool_quality_prompt_enabled" in PROMPT.read_text(encoding="utf-8")


def test_os_tqm_02_in_tier0():
    tier0 = TIER0.read_text(encoding="utf-8")
    assert "test_tool_quality_wiring.py" in tier0
    assert "test_horizon_os_tqm_02.py" in tier0


def test_os_tqm_02_closeout_exists():
    assert CLOSEOUT.is_file()
