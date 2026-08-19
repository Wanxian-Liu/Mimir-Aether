"""段 5 nudge→force 单测（2026-08-20 · B-Loki-Audit-1 修复验证）。

覆盖（任务书 S3 要求）：
- 条件满足（est_turns>=8 AND parallel_elig>=2 AND guard 通过）→ 注入**强制指令**（必须使用 delegate_task）
- 条件不满足（短任务 est<8）→ 无注入（None）
- 可并行度不达标（est≥8 但 parallel_elig<2）→ 无注入
- 反向清单拦截（含 commit）→ 无注入
- env 门控 MIMIR_DELEGATE_ENABLE=0 → 回退关闭（条件满足也不触发）
- env 未设置 → 默认开（条件满足触发）

运行：python3 -m pytest tests/agent/test_pi_trigger_force.py -v
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from agent.pi_trigger import PI_NUDGE_MARKER, maybe_pi_delegate_nudge  # noqa: E402

# guard 类别3 短上下文阈值（delegation_guard.SHORT_CONTEXT_TOKEN_THRESHOLD=10000——
# 显示层遮罩为 ***，算术探针实测 T*2=20000 确认）→ 测试需 padding ≥40000 字符
_GUARD_CTX_PAD = 50000


def _mk_messages(text: str, ctx_pad_chars: int = 0) -> list:
    """构造消息：最后一条 user 消息 = 任务书；可选 assistant 填充抬高上下文 token。"""
    msgs = [{"role": "user", "content": text}]
    if ctx_pad_chars:
        msgs.append({"role": "assistant", "content": "x" * ctx_pad_chars})
    return msgs


# 条件满足的正向任务书：est≈22≥8 + 三信号(多源/批量/独立) + 无反向清单命中 + 无强依赖链
FORCE_TASK = (
    "调研 OpenClaw 的角色库实现与 delegate 工具现状，分别搜索多源资料"
    "（web_search + web_extract 多 URL），批量验证全部 77 张 sources 页面"
    "与所有 plan.md 清单，逐项审计每条路径证据并交叉比对、汇总输出完整报告，"
    "同时整理独立子任务清单供并行派发"
)


def test_conditions_met_injects_force_instruction():
    """S3-①：条件满足（est≥8 AND parallel_elig≥2 AND guard 通过）→ 强制指令注入。"""
    out = maybe_pi_delegate_nudge(_mk_messages(FORCE_TASK, ctx_pad_chars=_GUARD_CTX_PAD))
    assert out is not None, "条件满足应注入强制指令（非 None）"
    assert PI_NUDGE_MARKER in out, "应保留 PI marker（注入通道标识）"
    assert "必须使用 delegate_task" in out, "应为强制指令而非建议（B-Loki-Audit-1）"
    assert "禁止自行串行执行" in out, "应包含禁止串行语义"
    assert "考虑" not in out and "建议" not in out, "强制指令不应再是 考虑/建议 语气"


def test_short_task_silent():
    """S3-②：条件不满足（est<8 短任务）→ 静默（None）。"""
    assert maybe_pi_delegate_nudge(_mk_messages("今天星期几")) is None
    assert maybe_pi_delegate_nudge(_mk_messages("ping 一下 baidu.com")) is None


def test_parallel_elig_fail_silent():
    """est≥8 但可并行度不达标（无 多源/批量/独立 信号）→ 静默。"""
    long_serial = (
        "审计今天的所有执行卡记录，扫描全部 wiki 目录下的清单文件，"
        "逐一核对全部记录内容是否完整，检查所有日志条目并整理归档，"
        "核对每条执行卡的状态字段与时间戳是否一致，清理全部过期记录，"
        "重新生成最新清单列表，确认所有字段完整后再汇总成一份完整清单文档"
    )
    # 先确认前置条件：est≥8（否则测试无效）
    from agent.pi_trigger import _estimate_turns

    assert _estimate_turns(long_serial) >= 8, "测试前提失败：est 应 ≥8"
    assert maybe_pi_delegate_nudge(_mk_messages(long_serial)) is None


def test_guard_block_silent():
    """反向清单拦截（类别4·commit）→ 静默。"""
    guarded_task = (
        "批量调研全部 77 张 sources 页面并分别验证多源资料，"
        "逐项审计每条路径证据后 git commit 汇总结果并推送"
    )
    assert maybe_pi_delegate_nudge(_mk_messages(guarded_task)) is None


def test_env_gate_zero_disables(monkeypatch):
    """S3-③：MIMIR_DELEGATE_ENABLE=0 → 回退关闭触发（条件满足也不注入）。"""
    monkeypatch.setenv("MIMIR_DELEGATE_ENABLE", "0")
    assert maybe_pi_delegate_nudge(_mk_messages(FORCE_TASK, ctx_pad_chars=_GUARD_CTX_PAD)) is None


def test_env_gate_default_on(monkeypatch):
    """MIMIR_DELEGATE_ENABLE 未设置 → 默认开（条件满足注入）。"""
    monkeypatch.delenv("MIMIR_DELEGATE_ENABLE", raising=False)
    out = maybe_pi_delegate_nudge(_mk_messages(FORCE_TASK, ctx_pad_chars=_GUARD_CTX_PAD))
    assert out is not None
    assert "必须使用 delegate_task" in out


def test_env_gate_false_variant_disables(monkeypatch):
    """MIMIR_DELEGATE_ENABLE=false（非 0 变体）→ 同样回退关闭。"""
    monkeypatch.setenv("MIMIR_DELEGATE_ENABLE", "false")
    assert maybe_pi_delegate_nudge(_mk_messages(FORCE_TASK, ctx_pad_chars=_GUARD_CTX_PAD)) is None
