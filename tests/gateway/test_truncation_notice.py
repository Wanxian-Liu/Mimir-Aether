"""架构硬规则 #2 截断通知边界测试（T3 · 2026-08-18 Hermes）

边界：截断 0 条（不注入）/ 正常截断（注入）/ 异常值（不注入）
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from gateway.agent_mixin import _format_truncation_notice


def test_zero_dropped_no_notice():
    """截断 0 条 → 不注入（无截断不打扰）"""
    assert _format_truncation_notice(0, 50) is None


def test_negative_dropped_no_notice():
    """负值（异常）→ 不注入（兜底）"""
    assert _format_truncation_notice(-3, 50) is None


def test_normal_truncation_notice():
    """正常截断 → 注入含条数与窗口"""
    out = _format_truncation_notice(42, 50)
    assert out is not None
    assert "42" in out and "50" in out
    assert "[CONTEXT TRUNCATED:" in out


def test_window_zero_no_notice():
    """窗口 0（异常）→ 不注入"""
    assert _format_truncation_notice(10, 0) is None
