"""Tests for agent/verify_before_report_guard — TD-04 空洞确认硬拦截.

8/17 论文任务失败根因：空洞确认模板（"收到——落盘"）无验证触发词，
verify guard 不拦截 → LLM 可无限绕过产出校验。
TD-04: _is_hollow_ack() 检测 + should_block_finish 分支（无工具调用即拦）。
"""
from __future__ import annotations

import sys
from pathlib import Path

# Add repo root so we can import the agent guard
_repo_root = Path(__file__).resolve().parent.parent.parent
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

from agent.verify_before_report_guard import (  # noqa: E402
    _is_hollow_ack,
    should_block_finish,
)


# ═══════════════════════════════════════════════════════════════════════════
# _is_hollow_ack — 空洞确认模板检测
# ═══════════════════════════════════════════════════════════════════════════

def test_hollow_ack_classic() -> None:
    """8/17 原型：「收到——补上写盘交付物」必须识别为空洞确认。"""
    assert _is_hollow_ack("收到——补上写盘交付物") is True


def test_hollow_ack_explore_promise() -> None:
    """「收到——探索结论先落盘」含探索+落盘承诺词 → 空洞确认。"""
    assert _is_hollow_ack("收到——探索结论先落盘") is True


def test_hollow_ack_record_promise() -> None:
    """「收到——把论文选择落盘」含落盘承诺词 → 空洞确认。"""
    assert _is_hollow_ack("收到——把论文选择落盘") is True


def test_hollow_ack_good_prefix() -> None:
    """「好的，我记录一下」→ 空洞确认（好 + 记录，无工具）。"""
    assert _is_hollow_ack("好的，我记录一下") is True


def test_hollow_ack_with_tool_action_not_hollow() -> None:
    """「收到，已调用 write_file 写入 /tmp/x.md」→ 有具体动作，非空洞。"""
    assert _is_hollow_ack("收到，已调用 write_file 写入 /tmp/x.md") is False


def test_hollow_ack_long_report_not_hollow() -> None:
    """长回复（≥80字）有实质内容 → 非空洞确认。"""
    long_text = "收到。我已经搜索了 arXiv 数学分类，找到 3 篇候选论文，其中最新的是 2608.14478，作者 Bennett Chow，主题是 Ricci 流热核的 Fisher 度量，详细分析如下……"
    assert _is_hollow_ack(long_text) is False


def test_hollow_ack_empty_not_hollow() -> None:
    """空文本 → 非空洞确认（无承诺词）。"""
    assert _is_hollow_ack("") is False
    assert _is_hollow_ack(None) is False  # type: ignore[arg-type]


def test_hollow_ack_question_not_hollow() -> None:
    """「收到，接下来怎么做？」→ 无承诺词 → 非空洞确认。"""
    assert _is_hollow_ack("收到，接下来怎么做？") is False


# ═══════════════════════════════════════════════════════════════════════════
# should_block_finish — 空洞确认无工具调用 → 必须拦截
# ═══════════════════════════════════════════════════════════════════════════

def _mk_messages(assistant_text: str, with_tool_call: bool = False) -> list[dict]:
    """构造最小 messages：user 任务 → assistant 空洞确认（可选 tool_calls）。"""
    msgs = [{"role": "user", "content": "去网上找一篇论文"}]
    if with_tool_call:
        msgs.append({
            "role": "assistant",
            "content": assistant_text,
            "tool_calls": [{
                "id": "call_1",
                "type": "function",
                "function": {"name": "web_search", "arguments": "{}"},
            }],
        })
    else:
        msgs.append({"role": "assistant", "content": assistant_text})
    return msgs


def test_block_hollow_ack_no_tool() -> None:
    """空洞确认 + 无工具调用 → should_block_finish 拦截（True）。"""
    msgs = _mk_messages("收到——补上写盘交付物")
    assert should_block_finish(msgs, "收到——补上写盘交付物") is True


def test_not_block_hollow_ack_with_tool() -> None:
    """空洞确认文本 + 有工具调用 → 不拦截（False，已实际执行）。"""
    msgs = _mk_messages("收到——补上写盘交付物", with_tool_call=True)
    assert should_block_finish(msgs, "收到——补上写盘交付物") is False


def test_not_block_normal_report() -> None:
    """正常执行回复（非空洞确认）→ 不拦截。"""
    text = "已找到论文 2608.14478，作者 Bennett Chow，主题 Ricci 流热核 Fisher 度量。"
    msgs = _mk_messages(text)
    assert should_block_finish(msgs, text) is False
