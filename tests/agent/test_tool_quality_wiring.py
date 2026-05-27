"""OS-TQM-02: ToolQualityManager default wiring and env gates."""

from __future__ import annotations

from pathlib import Path

import pytest

from agent.execution_pipeline import get_quality_manager, record_tool_call, start_execution_pipeline
from agent.execution_pipeline_sessions import reset_execution_pipeline_state
from agent.prompt_builder import build_tool_quality_guidance
from agent.tool_quality import ToolQualityManager, tool_quality_enabled, tool_quality_prompt_enabled


@pytest.fixture(autouse=True)
def _reset_pipeline() -> None:
    reset_execution_pipeline_state()
    yield
    reset_execution_pipeline_state()


def test_tool_quality_default_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MIMIR_TOOL_QUALITY", raising=False)
    assert tool_quality_enabled()
    assert tool_quality_prompt_enabled()


def test_tool_quality_env_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MIMIR_TOOL_QUALITY", "0")
    assert not tool_quality_enabled()
    assert not tool_quality_prompt_enabled()


def test_pipeline_skips_quality_mgr_when_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MIMIR_TOOL_QUALITY", "0")
    start_execution_pipeline(task_name="tqm-off", session_id="tqm-off")
    assert get_quality_manager("tqm-off") is None
    record_tool_call("read_file", {}, success=True, session_id="tqm-off")


def test_prompt_includes_degraded_when_enabled(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("MIMIR_AETHER_HOME", str(tmp_path))
    monkeypatch.setenv("MIMIR_TOOL_QUALITY", "1")
    (tmp_path / "data").mkdir(parents=True)
    db = tmp_path / "data" / "tool_quality.db"
    qm = ToolQualityManager(db_path=db, enable_persistence=True)
    for _ in range(5):
        qm.record("flaky_search", success=False, error_message="timeout")
    guidance = build_tool_quality_guidance()
    assert "flaky_search" in guidance
    assert "quality_score" in guidance


def test_prompt_omits_degraded_when_disabled(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("MIMIR_AETHER_HOME", str(tmp_path))
    monkeypatch.setenv("MIMIR_TOOL_QUALITY", "0")
    (tmp_path / "data").mkdir(parents=True)
    db = tmp_path / "data" / "tool_quality.db"
    qm = ToolQualityManager(db_path=db, enable_persistence=True)
    for _ in range(5):
        qm.record("flaky_search", success=False, error_message="timeout")
    assert build_tool_quality_guidance() == ""
