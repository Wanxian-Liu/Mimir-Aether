"""E-012 — post-pipeline JEPA run_cycle hook (env-gated, default off)."""

from __future__ import annotations

import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def test_jepa_env_off_does_not_spawn_thread(monkeypatch):
    monkeypatch.delenv("MIMIR_JEPA_CYCLE", raising=False)
    from agent.jepa_session_hook import schedule_post_close_jepa_cycle

    with patch("agent.jepa_session_hook.threading.Thread") as mock_thread:
        schedule_post_close_jepa_cycle(
            {"degraded_tools": [("skill_evolution", 0.2)]},
            session_id="sess-off",
        )
        mock_thread.assert_not_called()


def test_jepa_env_on_no_candidates_skips_run_cycle(monkeypatch):
    monkeypatch.setenv("MIMIR_JEPA_CYCLE", "1")
    from agent.jepa_session_hook import run_jepa_cycle_sync

    with patch("agent.jepa_session_hook.get_engine") as mock_get:
        reason = run_jepa_cycle_sync({}, session_id="sess-empty")
        mock_get.assert_not_called()
    assert reason == "no_candidates"


def test_jepa_env_on_with_degraded_tool_calls_run_cycle_once(monkeypatch):
    monkeypatch.setenv("MIMIR_JEPA_CYCLE", "1")
    monkeypatch.delenv("MIMIR_JEPA_RUN_TIER0", raising=False)
    from agent.jepa_session_hook import run_jepa_cycle_sync

    mock_engine = MagicMock()
    mock_engine.run_cycle.return_value = MagicMock(
        status="healthy",
        cycle_time_ms=12.5,
        summary="ok",
    )
    with patch("agent.jepa_session_hook.get_engine", return_value=mock_engine):
        reason = run_jepa_cycle_sync(
            {"degraded_tools": [("skill_evolution", 0.2)]},
            session_id="sess-degraded",
        )

    assert reason is None
    mock_engine.run_cycle.assert_called_once_with(
        ["skill_evolution.py"],
        execute_callback=None,
        run_tier0=False,
    )


def test_jepa_schedule_swallows_engine_exception(monkeypatch):
    monkeypatch.setenv("MIMIR_JEPA_CYCLE", "1")
    from agent.jepa_session_hook import schedule_post_close_jepa_cycle

    mock_engine = MagicMock()
    mock_engine.run_cycle.side_effect = RuntimeError("boom")

    with patch("agent.jepa_session_hook.get_engine", return_value=mock_engine):
        schedule_post_close_jepa_cycle(
            {"degraded_tools": [("skill_evolution", 0.1)]},
            session_id="sess-exc",
        )
        time.sleep(0.25)


def test_jepa_tier0_only_when_explicit_env(monkeypatch):
    monkeypatch.setenv("MIMIR_JEPA_CYCLE", "1")
    monkeypatch.setenv("MIMIR_JEPA_RUN_TIER0", "1")
    from agent.jepa_session_hook import run_jepa_cycle_sync

    mock_engine = MagicMock()
    mock_engine.run_cycle.return_value = MagicMock(
        status="healthy",
        cycle_time_ms=1.0,
        summary="ok",
    )
    with patch("agent.jepa_session_hook.get_engine", return_value=mock_engine):
        run_jepa_cycle_sync(
            {"degraded_tools": [("tool_quality", 0.3)]},
            session_id="sess-tier0",
        )

    mock_engine.run_cycle.assert_called_once_with(
        ["tool_quality.py"],
        execute_callback=None,
        run_tier0=True,
    )


def test_jepa_independent_of_auto_evolve(monkeypatch):
    monkeypatch.setenv("MIMIR_AUTO_EVOLVE", "1")
    monkeypatch.delenv("MIMIR_JEPA_CYCLE", raising=False)
    from agent.jepa_session_hook import run_jepa_cycle_sync

    with patch("agent.jepa_session_hook.get_engine") as mock_get:
        reason = run_jepa_cycle_sync(
            {"degraded_tools": [("skill_evolution", 0.2)]},
            session_id="sess-evolve-only",
        )
        mock_get.assert_not_called()
    assert reason == "env_off"
