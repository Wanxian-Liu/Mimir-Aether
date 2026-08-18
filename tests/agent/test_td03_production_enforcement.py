"""Tests for TD-03 产出校验三级强制（Hermes 代改 · 2026-08-18 四方批准）。

验证 L2/L3 判定核心：
1. research 实质回答豁免（≥50字 + 实词≥10 + 无未完成信号 + 无系统标记 → 视为产出）
2. 空洞确认（"收到——落盘"）不豁免 → 应被拦截
3. 含未完成信号（准备/接下来）不豁免
4. L2 硬拦截指令内容（明确 + 三选项）
5. TaskState.INTERRUPTED 存在（L3 中断状态）
"""
from __future__ import annotations

import sys
from pathlib import Path

_repo_root = Path(__file__).resolve().parent.parent.parent
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

from agent.task_state import TaskState  # noqa: E402
from agent.agent_loop import MimirAgentLoop  # noqa: E402


def _make_loop() -> MimirAgentLoop:
    """跳过 __init__ 直接构造实例（只测判定方法，不跑 loop）。"""
    return MimirAgentLoop.__new__(MimirAgentLoop)


# ═══════════════════════════════════════════════════════════════════════════
# research 实质回答豁免（TD-03 修订 1 · OpenClaw R4）
# ═══════════════════════════════════════════════════════════════════════════

def test_substantive_research_exempt() -> None:
    """≥50字实质 research 回答（实词足、无未完成信号）→ 豁免（视为产出）。"""
    loop = _make_loop()
    msgs = [
        {"role": "user", "content": "请调研阅文IP线下活动的可行性方案"},
        {"role": "assistant", "content": (
            "经过对证据01到11的逐一核查，阅文IP线下快闪业态增长显著，"
            "上半年同比增速超过两倍，沈阳大悦城以日系少女IP为主形成错位竞争空间，"
            "建议采用方案A的轻量快闪模式切入，预算控制在五十万以内，"
            "重点关注商圈客流与周末时段。"
        )},
    ]
    assert loop._is_substantive_research_answer(msgs) is True


def test_hollow_ack_not_exempt() -> None:
    """「收到——落盘」空洞确认（短、无实词）→ 不豁免（应被拦截）。"""
    loop = _make_loop()
    msgs = [
        {"role": "user", "content": "请调研阅文IP"},
        {"role": "assistant", "content": "收到——落盘"},
    ]
    assert loop._is_substantive_research_answer(msgs) is False


def test_unfinished_signal_not_exempt() -> None:
    """含「接下来/准备」未完成信号 → 不豁免（任务未完成）。"""
    loop = _make_loop()
    msgs = [
        {"role": "user", "content": "请调研阅文IP线下活动的可行性方案"},
        {"role": "assistant", "content": (
            "经过对证据01到11的逐一核查，阅文IP线下快闪业态增长显著，"
            "上半年同比增速超过两倍，沈阳大悦城以日系少女IP为主形成错位竞争空间，"
            "建议采用方案A的轻量快闪模式切入，接下来我准备补充预算明细。"
        )},
    ]
    assert loop._is_substantive_research_answer(msgs) is False


def test_system_mark_not_exempt() -> None:
    """含 [TODO]/[WAIT] 系统标记 → 不豁免。"""
    loop = _make_loop()
    msgs = [
        {"role": "user", "content": "请调研阅文IP线下活动的可行性方案"},
        {"role": "assistant", "content": (
            "经过对证据01到11的逐一核查，阅文IP线下快闪业态增长显著，"
            "上半年同比增速超过两倍，沈阳大悦城以日系少女IP为主形成错位竞争空间，"
            "建议采用方案A的轻量快闪模式切入，预算控制在五十万以内，[TODO]补预算明细。"
        )},
    ]
    assert loop._is_substantive_research_answer(msgs) is False


def test_short_answer_not_exempt() -> None:
    """<50字短回复 → 不豁免。"""
    loop = _make_loop()
    msgs = [
        {"role": "user", "content": "在吗"},
        {"role": "assistant", "content": "在的，有什么可以帮你？"},
    ]
    assert loop._is_substantive_research_answer(msgs) is False


# ═══════════════════════════════════════════════════════════════════════════
# L2 硬拦截指令（TD-03 修订 4 · OpenClaw R7）
# ═══════════════════════════════════════════════════════════════════════════

def test_hard_nudge_instruction_content() -> None:
    """L2 指令含拦截标识 + 三选项 + 防空洞确认。"""
    loop = _make_loop()
    nudge = loop._build_production_hard_nudge(0, 2)
    assert "production-enforce" in nudge
    assert "write_file/patch" in nudge
    assert "第 1/2 次" in nudge
    assert "空洞确认" in nudge


def test_hard_nudge_attempt_counter() -> None:
    """attempt 计数反映在消息里（第 2/2 次）。"""
    loop = _make_loop()
    nudge = loop._build_production_hard_nudge(1, 2)
    assert "第 2/2 次" in nudge


# ═══════════════════════════════════════════════════════════════════════════
# L3 中断状态（TD-03 修订 3 · OpenClaw R6）
# ═══════════════════════════════════════════════════════════════════════════

def test_task_state_interrupted_exists() -> None:
    """TaskState.INTERRUPTED 存在——L3 中断用，禁止标 DONE。"""
    assert TaskState.INTERRUPTED == "interrupted"
    assert TaskState.DONE != TaskState.INTERRUPTED


def test_interrupted_not_done() -> None:
    """消费方不得把 INTERRUPTED 当 DONE 处理。"""
    assert TaskState.INTERRUPTED.value != TaskState.DONE.value
