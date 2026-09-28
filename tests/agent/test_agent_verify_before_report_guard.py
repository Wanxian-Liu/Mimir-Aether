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


# ═══════════════════════════════════════════════════════════════════════════
# P0-2 回归（2026-09-28 · 闸门互斥）：execute_code 写交付卡 ⇒ guard **不拦**
# 病灶：本闸原先只认 WRITE_TOOLS（write_file/patch/…）⇒ `execute_code` 写盘的 run
#       被判「没写」⇒ 干完活仍被硬拦 + 回复被移出历史；而**空跑闸**同期判「写了」
#       ⇒ 两闸对**同一事实**相反判据 = 互斥（第 4 次空跑近因）。
# 修法：写动作判定**不重复实现** —— 单一真源 `empty_run_gate.classify_tool()`（内容级）。
# ═══════════════════════════════════════════════════════════════════════════
import json as _json  # noqa: E402

_P02_TASK = "任务：把审计结论**落盘**到讨论卡（写盘任务）"
_P02_ANSWER = "段落已追加，材料在盘上可核。"


def _p02_ec(code, tid="p2"):
    return {"role": "assistant", "content": "", "tool_calls": [
        {"id": tid, "type": "function",
         "function": {"name": "execute_code", "arguments": _json.dumps({"code": code})}}]}


def _p02_msgs(tool_call):
    return [
        {"role": "user", "content": _P02_TASK},
        tool_call,
        {"role": "tool", "tool_call_id": "p2", "content": "ok"},
    ]


def test_p0_2_exec_write_recognized_and_not_blocked(tmp_path) -> None:
    """目标：execute_code 真写交付卡 ⇒ 认到写 ∧ 不拦（修前此处必拦）。"""
    from agent.verify_before_report_guard import _has_written_this_turn
    card = tmp_path / "wiki" / "discussions" / "c.md"
    msgs = _p02_msgs(_p02_ec("open(%r,'a').write('y')" % str(card)))
    assert _has_written_this_turn(msgs) is True
    assert should_block_finish(msgs, _P02_ANSWER) is False


def test_p0_2_exec_readonly_still_blocks() -> None:
    """负控：execute_code 纯读 ⇒ 仍拦（内容级判据不得把只读读成写）。"""
    from agent.verify_before_report_guard import _has_written_this_turn
    msgs = _p02_msgs(_p02_ec("print(open('/tmp/x.log').read())"))
    assert _has_written_this_turn(msgs) is False
    assert should_block_finish(msgs, _P02_ANSWER) is True


def test_p0_2_mention_without_write_still_blocks(tmp_path) -> None:
    """配对负控：只在打印里提及卡路径（无写动作）⇒ 仍拦。"""
    from agent.verify_before_report_guard import _has_written_this_turn
    card = tmp_path / "wiki" / "discussions" / "c.md"
    msgs = _p02_msgs(_p02_ec("print('见 %s')" % str(card)))
    assert _has_written_this_turn(msgs) is False
    assert should_block_finish(msgs, _P02_ANSWER) is True


def test_p0_2_single_truth_source() -> None:
    """两闸同真源：guard 的分类器必须**就是** empty_run_gate.classify_tool。"""
    from agent import empty_run_gate as _erg
    from agent import verify_before_report_guard as _gd
    classify, _ = _gd._shared_classifier()
    assert classify is _erg.classify_tool
    assert "execute_code" in _gd.WRITE_CAPABLE_EXEC_TOOLS
    assert "terminal" in _gd.WRITE_CAPABLE_EXEC_TOOLS
