"""IQ-EVO-07: MIMIR_AUTO_ANALYSIS post-close hook."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


def test_post_analysis_skips_when_env_off(tmp_path, monkeypatch):
    monkeypatch.setenv("MIMIR_AETHER_HOME", str(tmp_path))
    monkeypatch.delenv("MIMIR_AUTO_ANALYSIS", raising=False)

    from agent.post_close_analysis import run_post_analysis_sync

    reason = run_post_analysis_sync({"errors": ["x"]}, task_name="t", session_id="s")
    assert reason == "env_off"


def test_post_analysis_skips_without_signal(tmp_path, monkeypatch):
    monkeypatch.setenv("MIMIR_AETHER_HOME", str(tmp_path))
    monkeypatch.setenv("MIMIR_AUTO_ANALYSIS", "1")

    from agent.post_close_analysis import run_post_analysis_sync

    reason = run_post_analysis_sync({}, task_name="t", session_id="s")
    assert reason == "no_signal"


def test_post_analysis_applies_llm_json(tmp_path, monkeypatch):
    monkeypatch.setenv("MIMIR_AETHER_HOME", str(tmp_path))
    monkeypatch.setenv("MIMIR_AUTO_ANALYSIS", "1")

    traj = tmp_path / "data" / "trajectories" / "sess.jsonl"
    traj.parent.mkdir(parents=True)
    traj.write_text(
        json.dumps(
            {
                "type": "session_start",
                "task_name": "iq07",
                "session_id": "iq07-sess",
                "start_time": "2026-05-25T00:00:00Z",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    pipeline_result = {
        "errors": [{"tool_name": "read_file", "message": "fail"}],
        "trajectory_path": str(traj),
        "quality_report": {},
    }

    analysis_payload = {
        "summary": "fixed read path",
        "overall_rating": 6,
        "tool_issues": [],
        "suggestions": [
            {
                "target": "read_file",
                "action": "fix",
                "reason": "retry",
                "priority": 2,
                "confidence": 0.8,
                "suggested_changes": "use absolute path",
            }
        ],
    }

    mock_response = MagicMock()
    mock_response.choices = [MagicMock(message=MagicMock(content=json.dumps(analysis_payload)))]

    from agent.execution_pipeline import start_execution_pipeline
    from agent.execution_pipeline_sessions import reset_execution_pipeline_state
    from agent.post_close_analysis import run_post_analysis_sync

    reset_execution_pipeline_state()
    start_execution_pipeline(task_name="iq07", session_id="iq07-sess")

    with patch("agent.auxiliary_client.call_llm", return_value=mock_response):
        reason = run_post_analysis_sync(
            pipeline_result,
            task_name="iq07",
            session_id="iq07-sess",
        )

    assert reason is None
    artifacts = list((tmp_path / "data" / "analysis_artifacts").glob("*.json"))
    assert artifacts


def test_schedule_post_close_analysis_spawns_thread(monkeypatch):
    monkeypatch.setenv("MIMIR_AUTO_ANALYSIS", "1")
    called = []

    def fake_schedule(result, *, task_name="", session_id=""):
        called.append((task_name, session_id))

    monkeypatch.setattr(
        "agent.post_close_analysis.run_post_analysis_sync",
        lambda *a, **k: called.append("ran") or None,
    )

    from agent.post_close_analysis import schedule_post_close_analysis

    schedule_post_close_analysis({"errors": ["e"]}, task_name="t", session_id="s")
    import time

    time.sleep(0.2)
    assert called
