"""P0-A 历史窗口单一真源测试（2026-09-10 上下文/Memory 体检修复）

验证 resolve_history_window() 优先级：env > config.yaml > 默认。

回归背景：config.yaml 写 context.max_recent_messages: 200，但 gateway 只读
env MIMIR_HISTORY_WINDOW（未设置 → 硬编码 50）→ 200 是死配置、实际生效 50，
且与 agent 侧（读 config）形成"双重截断 + 数值漂移"。
"""
import os
import sys
import textwrap

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import pytest

import gateway.agent_mixin as am


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    """确保 env 不存在，除非用例显式设置。"""
    monkeypatch.delenv("MIMIR_HISTORY_WINDOW", raising=False)


def _point_home(monkeypatch, tmp_path, yaml_text=None):
    """把 agent_mixin 的 _hermes_home 指向临时目录，可选写入 config.yaml。"""
    monkeypatch.setattr(am, "_hermes_home", tmp_path)
    if yaml_text is not None:
        (tmp_path / "config.yaml").write_text(
            textwrap.dedent(yaml_text), encoding="utf-8"
        )


def test_env_wins_over_config(monkeypatch, tmp_path):
    """env 优先级最高"""
    _point_home(monkeypatch, tmp_path, "context:\n  max_recent_messages: 200\n")
    monkeypatch.setenv("MIMIR_HISTORY_WINDOW", "42")
    assert am.resolve_history_window() == (42, "env:MIMIR_HISTORY_WINDOW")


def test_config_used_when_env_absent(monkeypatch, tmp_path):
    """核心回归：config 的 200 必须生效（修复前被硬编码 50 架空）"""
    _point_home(monkeypatch, tmp_path, "context:\n  max_recent_messages: 200\n")
    assert am.resolve_history_window() == (
        200,
        "config:context.max_recent_messages",
    )


def test_default_when_no_config_file(monkeypatch, tmp_path):
    """无 config.yaml → 默认值（且默认与 agent 侧对齐 = 200）"""
    _point_home(monkeypatch, tmp_path)
    assert am.resolve_history_window() == (am._DEFAULT_HISTORY_WINDOW, "default")
    assert am._DEFAULT_HISTORY_WINDOW == 200


def test_default_when_config_lacks_context_key(monkeypatch, tmp_path):
    """config 存在但无 context 段 → 默认值"""
    _point_home(monkeypatch, tmp_path, "model:\n  default: deepseek/deepseek-flash\n")
    assert am.resolve_history_window() == (am._DEFAULT_HISTORY_WINDOW, "default")


def test_zero_disables_window(monkeypatch, tmp_path):
    """窗口 0 = 禁用窗口（全量重放）语义保留"""
    _point_home(monkeypatch, tmp_path, "context:\n  max_recent_messages: 200\n")
    monkeypatch.setenv("MIMIR_HISTORY_WINDOW", "0")
    assert am.resolve_history_window() == (0, "env:MIMIR_HISTORY_WINDOW")


def test_invalid_env_falls_back_to_config(monkeypatch, tmp_path):
    """env 非法值 → 降级到 config（不再静默吞掉配置）"""
    _point_home(monkeypatch, tmp_path, "context:\n  max_recent_messages: 150\n")
    monkeypatch.setenv("MIMIR_HISTORY_WINDOW", "abc")
    assert am.resolve_history_window() == (
        150,
        "config:context.max_recent_messages",
    )


def test_corrupt_config_does_not_raise(monkeypatch, tmp_path):
    """config 损坏 → 降级默认，不阻断会话"""
    _point_home(monkeypatch, tmp_path, "context: [unclosed\n")
    assert am.resolve_history_window() == (am._DEFAULT_HISTORY_WINDOW, "default")
