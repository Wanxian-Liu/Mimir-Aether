"""2026-09-12 prompt-hint hygiene: min-sample gate + fixture exclusion.

背景：system prompt 的 "Tool quality signals" 块曾把测试夹具
（crash_tool 433/0、orphan_tool 430/0）与单样本工具当成生产遥测展示。
本文件锁定两条契约：
  1. get_degraded_tools(min_sample=N) 只放行 total_calls >= N 的工具；
  2. exclude_fixtures=True 时夹具工具永不出现（提示路径专用）；
  3. 默认 min_sample = 20，可经 env / tuned 覆盖；缺省时 get_degraded_tools
     保持既有行为（min_sample=3, exclude_fixtures=False）以免影响 evolution 调用。
"""

from __future__ import annotations

from pathlib import Path

import pytest

from agent.execution_pipeline_sessions import reset_execution_pipeline_state
from agent.prompt_builder import build_tool_quality_guidance
from agent.tool_quality import (
    ToolQualityManager,
    is_fixture_tool,
    prompt_min_sample,
)


@pytest.fixture(autouse=True)
def _reset() -> None:
    reset_execution_pipeline_state()
    yield
    reset_execution_pipeline_state()


def _mgr(tmp_path: Path) -> ToolQualityManager:
    (tmp_path / "data").mkdir(parents=True, exist_ok=True)
    return ToolQualityManager(
        db_path=tmp_path / "data" / "tool_quality.db", enable_persistence=True
    )


# ── min-sample gate ────────────────────────────────────────────────────────

def test_below_min_sample_is_excluded(tmp_path: Path) -> None:
    qm = _mgr(tmp_path)
    for _ in range(19):
        qm.record("flaky_search", success=False, error_message="timeout")
    assert qm.get_degraded_tools(threshold=0.5, min_sample=20) == []


def test_at_min_sample_is_included(tmp_path: Path) -> None:
    qm = _mgr(tmp_path)
    for _ in range(20):
        qm.record("flaky_search", success=False, error_message="timeout")
    names = [n for n, _ in qm.get_degraded_tools(threshold=0.5, min_sample=20)]
    assert names == ["flaky_search"]


def test_legacy_default_keeps_min_sample_3(tmp_path: Path) -> None:
    """调用方不传参时行为不变（evolution 路径依赖此语义）。"""
    qm = _mgr(tmp_path)
    for _ in range(3):
        qm.record("flaky_search", success=False, error_message="timeout")
    assert [n for n, _ in qm.get_degraded_tools(threshold=0.5)] == ["flaky_search"]


# ── fixture exclusion ──────────────────────────────────────────────────────

def test_fixture_names_recognized() -> None:
    assert is_fixture_tool("crash_tool")
    assert is_fixture_tool("ORPHAN_TOOL")
    assert not is_fixture_tool("read_file")


def test_fixture_excluded_from_prompt_hint(tmp_path: Path) -> None:
    qm = _mgr(tmp_path)
    for _ in range(50):
        qm.record("crash_tool", success=False, error_message="boom")
    excluded = qm.get_degraded_tools(
        threshold=0.5, min_sample=20, exclude_fixtures=True
    )
    assert excluded == []
    # 反向：不带 exclude_fixtures 时仍可见（不改动既有 evolution 语义）
    assert [n for n, _ in qm.get_degraded_tools(threshold=0.5, min_sample=20)] == [
        "crash_tool"
    ]


# ── prompt_min_sample resolution ───────────────────────────────────────────

def test_prompt_min_sample_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MIMIR_TOOL_QUALITY_MIN_SAMPLE", raising=False)
    assert prompt_min_sample() == 20


def test_prompt_min_sample_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MIMIR_TOOL_QUALITY_MIN_SAMPLE", "5")
    assert prompt_min_sample() == 5


def test_prompt_min_sample_garbage_env_falls_back(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MIMIR_TOOL_QUALITY_MIN_SAMPLE", "abc")
    assert prompt_min_sample() >= 1


# ── end-to-end: guidance never contains fixtures ───────────────────────────

def test_guidance_excludes_fixture_and_small_sample(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("MIMIR_AETHER_HOME", str(tmp_path))
    monkeypatch.setenv("MIMIR_TOOL_QUALITY", "1")
    monkeypatch.delenv("MIMIR_TOOL_QUALITY_MIN_SAMPLE", raising=False)
    qm = _mgr(tmp_path)
    for _ in range(50):
        qm.record("crash_tool", success=False, error_message="boom")
        qm.record("orphan_tool", success=False, error_message="boom")
    for _ in range(2):
        qm.record("vision_analyze", success=False, error_message="nope")
    assert build_tool_quality_guidance() == ""
