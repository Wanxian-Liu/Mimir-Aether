"""E-006 D6-0a — SessionTracker tool_calls SQL telemetry."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def test_session_tracker_records_tool_calls(tmp_path):
    from agent.session_tracker import SessionTracker

    db = tmp_path / "sessions.db"
    tracker = SessionTracker(db_path=str(db))

    tracker.record_tool_call("sess-a", "web_search", success=True, duration_ms=12.5)
    tracker.record_tool_call(
        "sess-a",
        "write_file",
        success=False,
        duration_ms=3.0,
        error_msg="NameError: is_truthy_value",
    )

    assert tracker.count_tool_calls() == 2
    assert tracker.count_tool_errors() == 1


def test_execution_pipeline_writes_tool_calls(tmp_path, monkeypatch):
    monkeypatch.setenv("MIMIR_AETHER_HOME", str(tmp_path))
    from agent.execution_pipeline import record_tool_call, start_execution_pipeline
    from agent.execution_pipeline_sessions import reset_execution_pipeline_state
    from agent.session_tracker import SessionTracker, get_session_tracker

    reset_execution_pipeline_state()
    get_session_tracker(db_path=str(tmp_path / "sessions.db"))

    start_execution_pipeline(task_name="t", session_id="pipe-sess")
    record_tool_call(
        "grep",
        {"pattern": "foo"},
        success=False,
        error_message="tool failed",
        duration_ms=8.0,
        session_id="pipe-sess",
    )

    tracker = SessionTracker(db_path=str(tmp_path / "sessions.db"))
    assert tracker.count_tool_errors() == 1
