"""IEVO-03 / D6-1: execution observability SoT (ADR-005)."""

from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
ADR = ROOT / "docs/adr/005-observability-execution-sot.md"


def test_adr005_accepted_and_names_execution_recorder_sot():
    assert ADR.is_file(), "missing docs/adr/005-observability-execution-sot.md"
    text = ADR.read_text(encoding="utf-8")
    assert "Accepted" in text
    assert "ExecutionRecorder" in text
    assert "execution_pipeline" in text


def test_execution_recorder_resolves_trajectories_under_mimir_data_dir():
    from agent.execution_recorder import _get_trajectory_dir
    from mimir_constants import get_mimir_data_dir

    assert _get_trajectory_dir() == get_mimir_data_dir() / "trajectories"


def test_execution_recorder_source_uses_mimir_constants_not_bare_env():
    text = (ROOT / "agent/execution_recorder.py").read_text(encoding="utf-8")
    assert "get_mimir_data_dir" in text
    assert 'os.getenv("MIMIR_AETHER_HOME"' not in text


def test_execution_pipeline_exposes_recorder_file_as_trajectory_path():
    text = (ROOT / "agent/execution_pipeline.py").read_text(encoding="utf-8")
    assert "session.recorder.file_path" in text
    assert 'result["trajectory_path"]' in text
