"""Test tool_event_emitter subscription/emit cycle."""
import os
from unittest.mock import patch as mock_patch


def test_emit_with_env_off():
    """When MIMIR_TOOL_EVENTS is off, subscribers should not receive events."""
    from agent.tool_event_emitter import (
        emit_tool_execution_end,
        emit_tool_execution_start,
        subscribe,
    )

    received = []
    token = subscribe(received.append)

    emit_tool_execution_start("read_file", {"path": "/tmp/x"}, session_id="s1")
    emit_tool_execution_end("read_file", success=True, duration_ms=10, session_id="s1")

    token()  # unsubscribe
    assert len(received) == 0, "should not emit when env is off"


def test_emit_env_on():
    """When MIMIR_TOOL_EVENTS=1, subscribers should receive both events."""
    with mock_patch.dict(os.environ, {"MIMIR_TOOL_EVENTS": "1"}):
        from agent.tool_event_emitter import (
            emit_tool_execution_end,
            emit_tool_execution_start,
            subscribe,
        )

        received = []
        token = subscribe(received.append)

        emit_tool_execution_start(
            "read_file", {"path": "/tmp/x"}, session_id="s1"
        )
        emit_tool_execution_end(
            "read_file", success=True, duration_ms=10.5, session_id="s1"
        )

        token()
        assert len(received) == 2

        start_ev = received[0]
        assert start_ev["type"] == "tool_execution_start"
        assert start_ev["tool_name"] == "read_file"
        assert start_ev["arguments"] == {"path": "/tmp/x"}
        assert start_ev["session_id"] == "s1"
        assert "timestamp" in start_ev

        end_ev = received[1]
        assert end_ev["type"] == "tool_execution_end"
        assert end_ev["tool_name"] == "read_file"
        assert end_ev["success"] is True
        assert end_ev["duration_ms"] == 10.5
        assert end_ev["session_id"] == "s1"


def test_emit_env_on_error():
    """Error path emits tool_execution_end with success=False and error."""
    with mock_patch.dict(os.environ, {"MIMIR_TOOL_EVENTS": "1"}):
        from agent.tool_event_emitter import (
            emit_tool_execution_end,
            subscribe,
        )

        received = []
        token = subscribe(received.append)

        emit_tool_execution_end(
            "crash_tool",
            success=False,
            duration_ms=0.5,
            session_id="s2",
            error="Something broke",
        )

        token()
        assert len(received) == 1
        ev = received[0]
        assert ev["type"] == "tool_execution_end"
        assert ev["success"] is False
        assert ev["error"] == "Something broke"


def test_subscriber_exception_does_not_break_others():
    """A failing subscriber should not prevent other subscribers from receiving."""
    with mock_patch.dict(os.environ, {"MIMIR_TOOL_EVENTS": "1"}):
        from agent.tool_event_emitter import (
            emit_tool_execution_start,
            subscribe,
        )

        received = []

        def failing(_event):
            raise RuntimeError("boom")

        token1 = subscribe(failing)
        token2 = subscribe(received.append)

        emit_tool_execution_start("tool_a", session_id="s3")

        token1()
        token2()
        assert len(received) == 1
        assert received[0]["tool_name"] == "tool_a"


def test_emit_empty_arguments():
    """When arguments is None, emit should not crash."""
    with mock_patch.dict(os.environ, {"MIMIR_TOOL_EVENTS": "1"}):
        from agent.tool_event_emitter import (
            emit_tool_execution_start,
            subscribe,
        )

        received = []
        token = subscribe(received.append)
        emit_tool_execution_start("tool_b", session_id="s4")
        token()
        assert len(received) == 1
        assert received[0]["arguments"] == {}
