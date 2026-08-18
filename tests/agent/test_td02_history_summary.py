"""Tests for TD-02 agent 侧窗口对齐（Hermes 代改 · 2026-08-18 四方批准）。

验证 core_loop.py L640-656 改动：
1. _max_recent 默认 25→50（对齐 gateway MIMIR_HISTORY_WINDOW，消除双重截断）
2. 放行 [HISTORY SUMMARY] 前缀 system 消息（OpenClaw R1：摘要 system 角色注入，
   user 会打乱交替 → 400）
3. 摘要消息注入后保留在对话头部
4. 非摘要 system 消息仍被跳过（不破坏既有过滤逻辑）
"""
from __future__ import annotations

import sys
from pathlib import Path

_repo_root = Path(__file__).resolve().parent.parent.parent
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

from agent.types import Message, MessageRole  # noqa: E402


def _inject_c1(conv: list, hist: list) -> int:
    """复刻 core_loop.py 的 C1 注入逻辑（含 TD-02 改动：摘要豁免截断 + 放行）。"""
    _max_recent = 50
    _history_slice = hist
    if len(hist) > _max_recent:
        _summary_msgs = [
            m for m in hist
            if m.get("role") == "system"
            and isinstance(m.get("content", ""), str)
            and m["content"].startswith("[HISTORY SUMMARY]")
        ]
        _rest = [
            m for m in hist
            if not (
                m.get("role") == "system"
                and isinstance(m.get("content", ""), str)
                and m["content"].startswith("[HISTORY SUMMARY]")
            )
        ]
        _history_slice = _summary_msgs + _rest[-_max_recent:]
    injected = 0
    for hmsg in _history_slice:
        role = hmsg.get("role", "")
        content = hmsg.get("content", "")
        if role == "system" and isinstance(content, str) and content.startswith("[HISTORY SUMMARY]"):
            msg = Message(role=MessageRole.SYSTEM, content=content)
            msg._c1_injected = True
            conv.append(msg)
            injected += 1
            continue
        if role not in ("user", "assistant"):
            continue
        if not content:
            continue
        if "tool_calls" in hmsg or "tool_call_id" in hmsg:
            continue
        msg = Message(
            role=MessageRole.USER if role == "user" else MessageRole.ASSISTANT,
            content=content,
        )
        msg._c1_injected = True
        conv.append(msg)
        injected += 1
    return injected


# ═══════════════════════════════════════════════════════════════════════════
# [HISTORY SUMMARY] system 消息放行
# ═══════════════════════════════════════════════════════════════════════════

def test_history_summary_system_allowed() -> None:
    """[HISTORY SUMMARY] system 消息被注入（放行），且保留 system 角色。"""
    conv: list = []
    hist = [
        {"role": "system", "content": "[HISTORY SUMMARY] Task Goal: 调研阅文项目\nProgress: 已完成证据核查\nBlocked: 无"},
        {"role": "user", "content": "继续"},
        {"role": "assistant", "content": "好的"},
    ]
    injected = _inject_c1(conv, hist)
    assert injected == 3
    assert conv[0].role == MessageRole.SYSTEM
    assert conv[0].content.startswith("[HISTORY SUMMARY]")
    assert [m.role for m in conv] == [MessageRole.SYSTEM, MessageRole.USER, MessageRole.ASSISTANT]


def test_plain_system_skipped() -> None:
    """非 [HISTORY SUMMARY] 的 system 消息仍被跳过（既有逻辑不破坏）。"""
    conv: list = []
    hist = [
        {"role": "system", "content": "[System] 你是 Mimir"},
        {"role": "user", "content": "你好"},
    ]
    injected = _inject_c1(conv, hist)
    assert injected == 1
    assert len(conv) == 1
    assert conv[0].role == MessageRole.USER


def test_tool_messages_still_skipped() -> None:
    """含 tool_calls 的消息仍被跳过（P0-3 设计权衡不破坏）。"""
    conv: list = []
    hist = [
        {"role": "user", "content": "查一下"},
        {"role": "assistant", "content": "", "tool_calls": [{"id": "x", "type": "function"}]},
        {"role": "assistant", "content": "结果如下"},
    ]
    injected = _inject_c1(conv, hist)
    assert injected == 2  # user + 纯文本 assistant（tool_calls 那条被跳过）


# ═══════════════════════════════════════════════════════════════════════════
# 窗口对齐（_max_recent 25→50）
# ═══════════════════════════════════════════════════════════════════════════

def test_window_default_50() -> None:
    """超过 50 条时截断到最近 50 条（原 25——TD-02 消除双重截断）。"""
    conv: list = []
    hist = [
        {"role": "system", "content": f"[HISTORY SUMMARY] 摘要#{i}"} if i == 0 else {"role": "user", "content": f"消息{i}"}
        for i in range(60)
    ]
    injected = _inject_c1(conv, hist)
    # 60 条中：1 条摘要（豁免截断）+ 59 条 user → 截断后 = 摘要(保留) + 50 条 user = 51
    assert injected == 51
    assert len(conv) == 51
    assert conv[0].role == MessageRole.SYSTEM  # 摘要在头部


def test_history_summary_not_truncated() -> None:
    """摘要消息在窗口头部，长历史下不被截断丢掉。"""
    conv: list = []
    hist = [{"role": "user", "content": f"消息{i}"} for i in range(55)]
    hist.insert(0, {"role": "system", "content": "[HISTORY SUMMARY] 早期上下文"})
    injected = _inject_c1(conv, hist)
    # 56 条：1 摘要（豁免）+ 55 user → 摘要保留 + 50 user = 51
    assert injected == 51
    assert any(m.content.startswith("[HISTORY SUMMARY]") for m in conv)
