"""IEVO-05 / D6-3: monitor + insights regression (≥3 behavioral tests)."""

from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _session_db(tmp_path):
    from mimir_state import SessionDB

    return SessionDB(db_path=tmp_path / "iev05_state.db")


def test_insights_sql_aggregates_tool_call_count_from_sessions(tmp_path):
    from agent.insights import InsightsEngine

    db = _session_db(tmp_path)
    db.create_session("s-a", "cli", model="test-model")
    db.append_message(
        "s-a",
        "assistant",
        content="",
        tool_calls=[{"id": "1", "function": {"name": "read_file", "arguments": "{}"}}],
    )
    db.append_message(
        "s-a",
        "assistant",
        content="",
        tool_calls=[
            {"id": "2", "function": {"name": "grep", "arguments": "{}"}},
            {"id": "3", "function": {"name": "grep", "arguments": "{}"}},
        ],
    )

    report = InsightsEngine(db).generate(days=30)
    assert not report.empty
    assert report.total_sessions == 1
    assert report.total_tool_calls == 3


def test_insights_tool_breakdown_from_tool_name_and_assistant_json(tmp_path):
    from agent.insights import InsightsEngine

    db = _session_db(tmp_path)
    db.create_session("s-b", "telegram", model="test-model")
    db.append_message("s-b", "tool", content="ok", tool_name="web_search")
    db.append_message("s-b", "tool", content="ok", tool_name="web_search")
    db.append_message(
        "s-b",
        "assistant",
        content="",
        tool_calls=[{"id": "x", "function": {"name": "write_file", "arguments": "{}"}}],
    )

    report = InsightsEngine(db).generate(days=30, source="telegram")
    assert not report.empty
    by_name = {t["tool"]: t["count"] for t in report.tools}
    assert by_name.get("web_search") == 2
    assert by_name.get("write_file") == 1


def test_insights_empty_sql_report_and_terminal_placeholder(tmp_path):
    from agent.insights import InsightsEngine

    db = _session_db(tmp_path)
    report = InsightsEngine(db).generate(days=7)
    assert report.empty is True
    assert report.total_tool_calls == 0
    text = InsightsEngine(db).format_terminal(report)
    assert "No sessions found" in text
    assert "7 days" in text


def test_monitor_ok_and_degraded_thresholds(tmp_path, monkeypatch):
    monkeypatch.setenv("MIMIR_AETHER_HOME", str(tmp_path))
    from agent.monitor import (
        get_agent_error_rate,
        get_agent_health_status,
        record_tool_outcome,
        reset_monitor_state,
        snapshot_for_health,
    )

    reset_monitor_state()
    for _ in range(8):
        record_tool_outcome("fast_tool", success=True, duration_ms=5.0)
    assert get_agent_error_rate() == 0.0
    assert get_agent_health_status() == "ok"
    snap = snapshot_for_health()
    assert snap["agent"] == "ok"
    assert snap["agent_error_rate"] == 0.0
    assert snap["agent_tool_p50_ms"] >= 5.0

    for _ in range(8):
        record_tool_outcome("bad_tool", success=False, error_message="fail")
    assert get_agent_error_rate() == 0.5
    assert get_agent_health_status() == "degraded"
    reset_monitor_state()


def test_insights_excludes_sessions_older_than_window(tmp_path):
    from agent.insights import InsightsEngine

    db = _session_db(tmp_path)
    old_start = time.time() - (40 * 86400)

    def _insert_old_session():
        def _do(conn):
            conn.execute(
                """INSERT INTO sessions (id, source, model, started_at, tool_call_count)
                   VALUES (?, ?, ?, ?, ?)""",
                ("old-s", "cli", "m", old_start, 99),
            )

        db._execute_write(_do)

    _insert_old_session()
    db.create_session("new-s", "cli", model="m")
    db.append_message(
        "new-s",
        "assistant",
        tool_calls=[{"id": "1", "function": {"name": "read_file", "arguments": "{}"}}],
    )

    report = InsightsEngine(db).generate(days=30)
    assert report.total_sessions == 1
    assert report.total_tool_calls == 1
