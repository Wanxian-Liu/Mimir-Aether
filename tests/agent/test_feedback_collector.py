"""Tests for agent.feedback_collector (IQ-EVO-16)."""

from __future__ import annotations

import json

import pytest

from agent import feedback_collector as fc


def test_disabled_by_default(monkeypatch, tmp_path):
    monkeypatch.delenv("MIMIR_FEEDBACK_COLLECTOR", raising=False)
    fc.reset_feedback_collector_state()
    fc.record_feedback_event("test", {"x": 1})
    assert fc.recent_feedback_events() == []


def test_records_when_enabled(monkeypatch, tmp_path):
    monkeypatch.setenv("MIMIR_FEEDBACK_COLLECTOR", "1")
    monkeypatch.setenv("MIMIR_AETHER_HOME", str(tmp_path))
    fc.reset_feedback_collector_state()
    fc.record_tool_outcome_feedback(
        "read_file",
        success=False,
        error_message="ENOENT",
        session_id="sess-1",
    )
    events = fc.recent_feedback_events()
    assert len(events) == 1
    assert events[0]["event_type"] == "tool_failure"
    log_path = tmp_path / "data" / "feedback_events.jsonl"
    assert log_path.is_file()
    row = json.loads(log_path.read_text(encoding="utf-8").strip().splitlines()[-1])
    assert row["payload"]["tool_name"] == "read_file"
