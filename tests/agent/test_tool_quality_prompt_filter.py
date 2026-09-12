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

import json
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


# ── W-①（2026-09-12 刘哥批）：tuned 键注册 + env>tuned>20 链路实测 ──────────
# 回归背景：该键此前**未注册**于 tuned_thresholds._REGISTRY，
# prompt_min_sample() 调 get_tuned_float() 必抛 KeyError（被吞）→
# 文档宣称的 env>tuned>20 中间环节是死链（R-① 收窄时实测暴露）。

def _write_override(home: Path, key: str, value: object) -> None:
    data = home / "data"
    data.mkdir(parents=True, exist_ok=True)
    (data / "tuned_thresholds.json").write_text(
        json.dumps({"updated_at": 0, "overrides": {key: value}}), encoding="utf-8"
    )


def test_prompt_min_sample_tuned_key_is_registered() -> None:
    """键必须在 registry 内 —— 否则中间环节恒为死链。"""
    from agent.tuned_thresholds import registry_keys

    assert "tool_quality.prompt_min_sample" in registry_keys()


def test_prompt_min_sample_tuned_default_matches_module_default() -> None:
    """registry default 与 _DEFAULT_PROMPT_MIN_SAMPLE 必须同值（防两处漂移）。"""
    from agent.tuned_thresholds import get_tuned_int

    assert get_tuned_int("tool_quality.prompt_min_sample") == 20


def test_prompt_min_sample_tuned_override_wins(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("MIMIR_AETHER_HOME", str(tmp_path))
    monkeypatch.delenv("MIMIR_TOOL_QUALITY_MIN_SAMPLE", raising=False)
    _write_override(tmp_path, "tool_quality.prompt_min_sample", 8)
    assert prompt_min_sample() == 8


def test_prompt_min_sample_tuned_override_clamped_to_min(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """越界 override 被有界 clamp —— 不允许把门槛压到 1（等于关闭闸门）。"""
    monkeypatch.setenv("MIMIR_AETHER_HOME", str(tmp_path))
    monkeypatch.delenv("MIMIR_TOOL_QUALITY_MIN_SAMPLE", raising=False)
    _write_override(tmp_path, "tool_quality.prompt_min_sample", 1)
    assert prompt_min_sample() == 8


def test_prompt_min_sample_env_beats_tuned(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("MIMIR_AETHER_HOME", str(tmp_path))
    monkeypatch.setenv("MIMIR_TOOL_QUALITY_MIN_SAMPLE", "33")
    _write_override(tmp_path, "tool_quality.prompt_min_sample", 8)
    assert prompt_min_sample() == 33


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


# ── R-② 单一真源 + R-① 窄异常 + R2 观测点（2026-09-12 审计整改）────────────

_CANONICAL_FIXTURE_NAMES = {
    "calc",
    "crash_tool",
    "echo",
    "nonexistent",
    "noop_tool",
    "orphan_tool",
    "tool_a",
    "tool_b",
}
_REAL_TOOL_NAMES = (
    "read_file",
    "session_search",
    "terminal",
    "execute_code",
    "write_file",
    "patch",
    "web_search",
)


def test_fixture_name_set_is_canonical() -> None:
    from agent.tool_quality import _FIXTURE_TOOL_NAMES

    assert set(_FIXTURE_TOOL_NAMES) == _CANONICAL_FIXTURE_NAMES


def test_real_tools_are_never_fixtures() -> None:
    """BUG-08 教训守卫：真实工具永不进夹具名单。"""
    for name in _REAL_TOOL_NAMES:
        assert not is_fixture_tool(name)


def test_fixture_names_have_single_live_definition() -> None:
    """R-② 守卫：除 agent/tool_quality.py 外，活代码不得再定义夹具名单。

    docs/archive/ 下的世界模型死代码（_SELF_HEAL_EXCLUDE）不计——不参与运行时、
    不被任何活模块 import。
    """
    root = Path(__file__).resolve().parents[2]
    offenders = []
    for sub in ("agent", "gateway", "tools", "core"):
        base = root / sub
        if not base.is_dir():
            continue
        for path in base.rglob("*.py"):
            if "test" in path.name:
                continue
            rel = path.relative_to(root).as_posix()
            if rel == "agent/tool_quality.py":
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            if "_SELF_HEAL_EXCLUDE" in text or (
                "crash_tool" in text and "orphan_tool" in text
            ):
                offenders.append(rel)
    assert offenders == []


def test_tuned_reads_are_not_silently_swallowed() -> None:
    """R-① 契约：tuned 读取段不得再出现裸 except Exception: pass。"""
    src = (Path(__file__).resolve().parents[2] / "agent" / "tool_quality.py").read_text(
        encoding="utf-8"
    )
    assert "except Exception:\n        pass" not in src
    assert "MIMIR_TOOL_QUALITY_MIN_SAMPLE" in src  # env 段仍在
    # 未注册键走显式 KeyError 分支（不是裸 Exception 吞咽）
    assert "ImportError, KeyError" in src


def test_resolved_params_logged_once_per_change(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """R2：同参不重复记，参数变化再记一行。"""
    import logging as _logging

    from agent import prompt_builder as pb

    pb._TQ_LAST_RESOLVED = None
    with caplog.at_level(_logging.INFO, logger="agent.prompt_builder"):
        pb._log_tool_quality_resolution(0.3, 20, 1)
        pb._log_tool_quality_resolution(0.3, 20, 5)  # 同参 → 不重复
        pb._log_tool_quality_resolution(0.3, 5, 1)  # 参数变 → 再记
    lines = [r.getMessage() for r in caplog.records if "resolved_threshold" in r.getMessage()]
    pb._TQ_LAST_RESOLVED = None
    assert len(lines) == 2
    assert "resolved_min_sample=20" in lines[0]
    assert "resolved_min_sample=5" in lines[1]
