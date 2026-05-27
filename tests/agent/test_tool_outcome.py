"""IQ-EVO-48: infer_tool_success for soft tool failures."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from agent.tool_outcome import infer_tool_success


def test_infer_tool_success_json_error_key():
    ok, msg = infer_tool_success(json.dumps({"error": "File not found"}))
    assert ok is False
    assert "File not found" in msg


def test_infer_tool_success_normal_result():
    ok, msg = infer_tool_success(json.dumps({"items": [1, 2], "count": 2}))
    assert ok is True
    assert msg == ""


def test_infer_tool_success_invalid_json():
    ok, msg = infer_tool_success("not json at all")
    assert ok is True
    assert msg == ""


def test_infer_tool_success_false_flag():
    ok, msg = infer_tool_success(
        json.dumps({"error": "bad", "success": False})
    )
    assert ok is False
    assert msg


def test_soft_failure_recorded_for_extract_errors(tmp_path, monkeypatch):
    """Soft failure → trajectory success=false → extract_errors on close."""
    monkeypatch.setenv("MIMIR_AETHER_HOME", str(tmp_path))

    from agent.execution_pipeline import (
        close_execution_pipeline,
        record_tool_call,
        start_execution_pipeline,
    )
    from agent.execution_pipeline_sessions import reset_execution_pipeline_state
    from agent.execution_recorder import extract_errors
    from tools.registry import tool_error

    reset_execution_pipeline_state()
    start_execution_pipeline(task_name="iq48", session_id="iq48-sess")
    err_text = tool_error("File not found")
    ok, err_msg = infer_tool_success(err_text)
    assert ok is False
    record_tool_call(
        "read_file",
        {"path": "/missing"},
        success=ok,
        error_message=err_msg,
        session_id="iq48-sess",
    )
    result = close_execution_pipeline(session_id="iq48-sess")
    assert result.get("errors")
    traj = Path(result["trajectory_path"])
    extracted = extract_errors(traj)
    assert extracted
    assert extracted[0].get("success") is False
