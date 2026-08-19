"""P1-1 v2 测试：Loki 10 边界用例复测（漏触发率 <20%）+ 负向 10 例（0 误触发）。

2026-08-19 Mimir 第 4 项 —— 验证标准来自执行卡：
"用 Loki 10 边界用例复测——漏触发率 <20%"

运行：pytest tests/agent/test_pi_trigger_v2.py -q
"""
import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "agent"))

from pi_trigger import _estimate_turns  # noqa: E402

# Loki 10 边界用例（来源：2026-08-19-四方审计-Mimir性能迭代质量.md 1.1 节）
# (用例ID, 任务文本, 应触发)
LOKI_CASES = [
    ("L1", "帮我查一下今天天气", False),
    ("L2", "审计77 张 sources 页面", True),
    ("L3", "扫一遍 wiki 讨论卡", True),
    ("L4", "整理所有 plan.md", True),
    ("L5", "把所有 sources 实体化到 wiki/concepts/", True),
    ("F1", "调研 OpenClaw 的角色库实现，每条都要 path + 核心规则", True),
    ("F2", "review commit 9d61bd9改动的实体保留率验证钩子 + 实测确认 ≥80% 是否真生效", True),
    ("F3", "审计今天的所有执行卡，给出 🔴🟡🟢 三档分类 + 路径证据", True),
    ("F4", "Loki视角出图任务完整清单：" + "，".join(["执行wiki扫描并输出全部报告"] * 5) + " 汇总所有sources页面的路径证据", True),
    ("F5", "把 wiki/concepts/Loki审计模板.md 全文跑一遍 + 4问清单逐项验证 + 出报告", True),
]

# 负向 10 例（全部不应触发）
NEG_CASES = [
    "今天星期几",
    "ping 一下 baidu.com",
    "git status",
    "读一下 MEMORY.md L50",
    "写一段 hello world",
    "echo hi",
    "ls -la",
    "rm -f tmp.txt",
    "git log -5",
    "cat README.md",
]

MIN_TURNS = 8


@pytest.mark.parametrize("cid,text,expect_trigger", LOKI_CASES, ids=[c[0] for c in LOKI_CASES])
def test_loki_boundary_case(cid, text, expect_trigger):
    """Loki 10 边界用例：漏触发率 <20% 验证标准。"""
    est = _estimate_turns(text)
    triggered = est >= MIN_TURNS
    assert triggered == expect_trigger, (
        f"{cid} 期望{'触发' if expect_trigger else '不触发'}但 est={est} "
        f"{'未触发（漏触发）' if expect_trigger and not triggered else '误触发'}"
    )


def test_loki_miss_rate_below_20pct():
    """整体漏触发率 <20%（执行卡验证标准）。"""
    miss = sum(
        1 for cid, text, expect in LOKI_CASES
        if (_estimate_turns(text) >= MIN_TURNS) != expect
    )
    assert miss / len(LOKI_CASES) < 0.20, f"漏触发率 {miss}/{len(LOKI_CASES)} = {miss/len(LOKI_CASES):.0%} ≥ 20%"


@pytest.mark.parametrize("text", NEG_CASES, ids=[f"neg{i}" for i in range(len(NEG_CASES))])
def test_negative_no_false_trigger(text):
    """负向用例：0 误触发。"""
    est = _estimate_turns(text)
    assert est < MIN_TURNS, f"负向用例误触发: est={est} >= {MIN_TURNS} | {text}"


def test_negative_false_trigger_rate_zero():
    """负向整体误触发率 = 0。"""
    false_pos = sum(1 for text in NEG_CASES if _estimate_turns(text) >= MIN_TURNS)
    assert false_pos == 0, f"误触发 {false_pos}/{len(NEG_CASES)}"
