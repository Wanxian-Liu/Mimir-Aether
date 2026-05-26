"""Horizon Wave 4 (IQ-EVO-15～18) contract."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKLOG = ROOT / "docs/MIMIR_EXEC_BACKLOG.md"
WAVE4_PLAN = ROOT / "docs/phase0/p2-long-iqevo-wave4.md"
FEEDBACK = ROOT / "agent/feedback_collector.py"
PROMPT = ROOT / "agent/prompt_builder.py"
MONITOR = ROOT / "agent/monitor.py"
PIPELINE = ROOT / "agent/execution_pipeline.py"
POST_ANALYSIS = ROOT / "agent/post_close_analysis.py"
TIER0 = ROOT / "run_ralph_tier0.sh"

WAVE4_ENGINEERING_IDS = (
    "IQ-EVO-16",
    "IQ-EVO-17",
    "IQ-EVO-18",
)


def test_wave4_plan_exists():
    assert WAVE4_PLAN.is_file()
    text = WAVE4_PLAN.read_text(encoding="utf-8")
    assert "MIMIR_FEEDBACK_COLLECTOR" in text
    assert "AUTO_EVOLVE" in text


def test_feedback_collector_module():
    text = FEEDBACK.read_text(encoding="utf-8")
    assert "record_feedback_event" in text
    assert "feedback_events.jsonl" in text


def test_tool_quality_guidance_in_prompt_builder():
    text = PROMPT.read_text(encoding="utf-8")
    assert "build_tool_quality_guidance" in text
    assert "read-only" in text.lower() or "read-only" in text


def test_hooks_wired():
    assert "record_tool_outcome_feedback" in MONITOR.read_text(encoding="utf-8")
    assert "record_pipeline_close_feedback" in PIPELINE.read_text(encoding="utf-8")
    assert "record_analysis_artifact_feedback" in POST_ANALYSIS.read_text(encoding="utf-8")


def test_backlog_wave4_section():
    text = BACKLOG.read_text(encoding="utf-8")
    assert "Wave 4" in text
    for item in WAVE4_ENGINEERING_IDS:
        assert f"**{item}**" in text


def test_wave4_contract_in_tier0():
    assert "tests/contract/test_horizon_iqevo_wave4.py" in TIER0.read_text(encoding="utf-8")
