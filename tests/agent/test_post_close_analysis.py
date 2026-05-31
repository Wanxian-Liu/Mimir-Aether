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


def test_post_analysis_evolution_after_close_without_session(tmp_path, monkeypatch):
    """IQ-EVO-40: async analysis worker applies SKILL writes without pipeline session."""
    monkeypatch.setenv("MIMIR_AETHER_HOME", str(tmp_path))
    monkeypatch.setenv("MIMIR_AUTO_ANALYSIS", "1")
    monkeypatch.setenv("MIMIR_AUTO_EVOLVE", "1")

    skills_dir = tmp_path / "skills"
    skill_dir = skills_dir / "async-evolve-skill"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("# before async\n", encoding="utf-8")
    monkeypatch.setattr("mimir_constants.get_skills_dir", lambda: skills_dir)

    traj = tmp_path / "data" / "trajectories" / "async-sess.jsonl"
    traj.parent.mkdir(parents=True)
    traj.write_text(
        json.dumps(
            {
                "type": "session_start",
                "task_name": "iq40",
                "session_id": "iq40-sess",
                "start_time": "2026-05-26T00:00:00Z",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    from agent.execution_pipeline import (
        close_execution_pipeline,
        start_execution_pipeline,
    )
    from agent.execution_pipeline_sessions import reset_execution_pipeline_state
    from agent.post_close_analysis import run_post_analysis_sync

    reset_execution_pipeline_state()
    start_execution_pipeline(task_name="iq40", session_id="iq40-sess")
    pipeline_result = close_execution_pipeline(session_id="iq40-sess")
    assert pipeline_result.get("trajectory_path")
    assert not pipeline_result.get("_evolution_suggestion_objs")
    pipeline_result["errors"] = [{"tool_name": "read_file", "message": "fail"}]

    analysis_payload = {
        "summary": "tool failed",
        "overall_rating": 5,
        "tool_issues": [],
        "suggestions": [
            {
                "target": "async-evolve-skill",
                "action": "fix",
                "reason": "repair",
                "suggested_changes": "# after async\n",
                "priority": 1,
                "confidence": 0.9,
            }
        ],
    }
    mock_response = MagicMock()
    mock_response.choices = [
        MagicMock(message=MagicMock(content=json.dumps(analysis_payload)))
    ]

    with patch("agent.auxiliary_client.call_llm", return_value=mock_response):
        reason = run_post_analysis_sync(
            pipeline_result,
            task_name="iq40",
            session_id="iq40-sess",
        )

    assert reason is None
    assert "# after async" in (skill_dir / "SKILL.md").read_text(encoding="utf-8")


def test_post_analysis_skips_evolution_on_production_home(monkeypatch, tmp_path):
    """Synthetic iq40 session must not apply evolution when home is ~/.mimiraether."""
    prod = Path.home() / ".mimiraether"
    monkeypatch.setenv("MIMIR_AETHER_HOME", str(prod))
    monkeypatch.setenv("HERMES_HOME", str(prod))
    monkeypatch.setenv("MIMIR_AUTO_ANALYSIS", "1")
    monkeypatch.setenv("MIMIR_AUTO_EVOLVE", "1")

    pipeline_result = {
        "errors": [{"tool_name": "read_file", "message": "fail"}],
        "trajectory_path": str(tmp_path / "missing-traj.jsonl"),
        "quality_report": {},
    }
    analysis_payload = {
        "summary": "x",
        "overall_rating": 5,
        "tool_issues": [],
        "suggestions": [
            {
                "target": "read_file",
                "action": "fix",
                "reason": "r",
                "suggested_changes": "c",
                "priority": 1,
                "confidence": 0.9,
            }
        ],
    }
    mock_response = MagicMock()
    mock_response.choices = [
        MagicMock(message=MagicMock(content=json.dumps(analysis_payload)))
    ]

    from agent.post_close_analysis import run_post_analysis_sync

    with patch("agent.auxiliary_client.call_llm", return_value=mock_response):
        with patch(
            "agent.execution_pipeline.apply_evolution_from_analysis"
        ) as mock_evo:
            run_post_analysis_sync(
                pipeline_result,
                task_name="iq40",
                session_id="iq40-sess",
            )
            mock_evo.assert_not_called()


def test_post_analysis_skips_evolution_when_auto_evolve_off(tmp_path, monkeypatch):
    monkeypatch.setenv("MIMIR_AETHER_HOME", str(tmp_path))
    monkeypatch.setenv("MIMIR_AUTO_ANALYSIS", "1")
    monkeypatch.delenv("MIMIR_AUTO_EVOLVE", raising=False)

    skills_dir = tmp_path / "skills"
    skill_dir = skills_dir / "no-evolve-skill"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("# before\n", encoding="utf-8")
    monkeypatch.setattr("mimir_constants.get_skills_dir", lambda: skills_dir)

    traj = tmp_path / "data" / "trajectories" / "no-evolve.jsonl"
    traj.parent.mkdir(parents=True)
    traj.write_text(
        json.dumps({"type": "session_start", "session_id": "ne-sess"}) + "\n",
        encoding="utf-8",
    )

    from agent.execution_pipeline import apply_evolution_from_analysis
    from agent.post_analysis import ExecutionAnalysis, EvolutionSuggestion

    analysis = ExecutionAnalysis(
        suggestions=[
            EvolutionSuggestion(
                target="no-evolve-skill",
                action="fix",
                suggested_changes="# should not apply\n",
            )
        ]
    )
    results = apply_evolution_from_analysis(analysis, skills_dir=skills_dir)
    assert results == []
    assert (skill_dir / "SKILL.md").read_text(encoding="utf-8") == "# before\n"


def test_post_analysis_fallback_suggestion_when_llm_empty(tmp_path, monkeypatch):
    """IQ-EVO-48: errors + empty LLM suggestions → one fix fallback → evolution."""
    monkeypatch.setenv("MIMIR_AETHER_HOME", str(tmp_path))
    monkeypatch.setenv("MIMIR_AUTO_ANALYSIS", "1")
    monkeypatch.setenv("MIMIR_AUTO_EVOLVE", "1")

    skills_dir = tmp_path / "skills"
    skill_dir = skills_dir / "fallback-evolve-skill"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("# before fallback\n", encoding="utf-8")
    monkeypatch.setattr("mimir_constants.get_skills_dir", lambda: skills_dir)

    traj = tmp_path / "data" / "trajectories" / "fb-sess.jsonl"
    traj.parent.mkdir(parents=True)
    traj.write_text(
        json.dumps(
            {
                "type": "session_start",
                "task_name": "iq48",
                "session_id": "fb-sess",
                "start_time": "2026-05-26T00:00:00Z",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    analysis_payload = {
        "summary": "no suggestions from model",
        "overall_rating": 4,
        "tool_issues": [],
        "suggestions": [],
    }
    mock_response = MagicMock()
    mock_response.choices = [
        MagicMock(message=MagicMock(content=json.dumps(analysis_payload)))
    ]

    pipeline_result = {
        "errors": [{"tool_name": "fallback-evolve-skill", "message": "fail"}],
        "trajectory_path": str(traj),
        "quality_report": {},
    }

    from agent.post_close_analysis import run_post_analysis_sync

    with patch("agent.auxiliary_client.call_llm", return_value=mock_response):
        reason = run_post_analysis_sync(
            pipeline_result,
            task_name="iq48",
            session_id="fb-sess",
        )

    assert reason is None
    assert (skill_dir / "SKILL.md").read_text(encoding="utf-8") != "# before fallback\n"


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
