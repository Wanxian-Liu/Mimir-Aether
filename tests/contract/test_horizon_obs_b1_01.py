"""Horizon B1 · OBS-B1-01 — ObservabilityBus evaluate + defer (ADR-007)."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ADR007 = ROOT / "docs/adr/007-observability-bus-defer.md"
ADR005 = ROOT / "docs/adr/005-observability-execution-sot.md"
PIPELINE = ROOT / "agent/execution_pipeline.py"
BACKLOG = ROOT / "docs/MIMIR_EXEC_BACKLOG.md"
TIER0 = ROOT / "run_ralph_tier0.sh"


def test_adr007_defers_observability_bus():
    assert ADR007.is_file()
    text = ADR007.read_text(encoding="utf-8")
    assert "defer" in text.lower()
    assert "record_tool_call" in text
    assert ADR005.name in text or "ADR-005" in text


def test_record_tool_call_retains_fail_open_fanout():
    text = PIPELINE.read_text(encoding="utf-8")
    assert "def record_tool_call" in text
    assert "get_session_tracker" in text
    assert "record_tool_outcome" in text
    assert "ExecutionRecorder" in text or "recorder.record_tool_call" in text


def test_adr005_still_names_execution_recorder_sot():
    text = ADR005.read_text(encoding="utf-8")
    assert "ExecutionRecorder" in text
    assert "Accepted" in text


def test_backlog_obs_b1_01_present():
    text = BACKLOG.read_text(encoding="utf-8")
    assert "**OBS-B1-01**" in text
    assert "Horizon B1" in text


def test_obs_b1_01_contract_in_tier0():
    assert "tests/contract/test_horizon_obs_b1_01.py" in TIER0.read_text(encoding="utf-8")
