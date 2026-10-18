"""梦境蒸馏写回面持久化契约（2026-10-18 · 刘哥批 D1/D2/D3）。

背景（实测取证）：2026-10-18 蒸馏后 behavioral_constraints 丢掉一条防护规则
（写回整表替换 + 旧约束从未进入提示词 ⇒ 每晚从零重算，丢不留痕）；
persistent.json 49/49 条目 AKL 字段丢失（LLM 不输出 ⇒ setdefault 补默认值
⇒ 人工调过的权重被抹平、衰减锚点每晚重置）。

三条契约：
  C1 文本未变 ⇒ AKL 字段继承旧值
  C2 文本已改写 ⇒ 不继承（宁可丢权重，不可错配权重）
  C3 约束：旧的先占位、新的补位、被挤掉的必须显式返回（不静默）
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from agent.dream_memory import (  # noqa: E402
    _format_memory_for_distillation,
    _inherit_akl,
    _merge_constraints,
)

# ── C1 / C2：AKL 字段继承 ───────────────────────────────────────────


def test_c1_identical_text_inherits_akl_fields():
    old = [{"decision": "先落盘再汇报", "importance": 90, "maturity": "stable",
            "last_access": "2026-01-01T00:00:00+00:00", "decay_factor": 0.8}]
    new = [{"decision": "先落盘再汇报", "tip_type": "strategy"}]
    out, n = _inherit_akl(old, new, "decision")
    assert out[0]["importance"] == 90
    assert out[0]["maturity"] == "stable"
    assert out[0]["decay_factor"] == 0.8
    assert out[0]["last_access"] == "2026-01-01T00:00:00+00:00"
    assert n == 4
    assert out[0]["tip_type"] == "strategy"


def test_c1b_whitespace_only_difference_still_inherits():
    old = [{"pattern": "声明与盘上状态解耦", "importance": 77}]
    new = [{"pattern": "  声明与盘上状态解耦  "}]
    out, _ = _inherit_akl(old, new, "pattern")
    assert out[0]["importance"] == 77


def test_c2_rewritten_text_does_not_inherit():
    """负控：文本变了就不许继承——错配权重比丢权重更坏。"""
    old = [{"decision": "旧决策全文", "importance": 90}]
    new = [{"decision": "被 LLM 改写过的决策全文"}]
    out, n = _inherit_akl(old, new, "decision")
    assert "importance" not in out[0]
    assert n == 0


def test_c2b_no_old_items_is_noop():
    out, n = _inherit_akl([], [{"decision": "x"}], "decision")
    assert n == 0 and out[0] == {"decision": "x"}


def test_c1c_new_item_own_akl_wins_over_old():
    old = [{"decision": "d", "importance": 10}]
    new = [{"decision": "d", "importance": 99}]
    out, _ = _inherit_akl(old, new, "decision")
    assert out[0]["importance"] == 99


# ── C3：约束合并 ────────────────────────────────────────────────────


def test_c3_old_constraint_survives_when_llm_omits_it():
    old = [{"rule": "你不应该把探针失效读成事实", "source": "distilled"}]
    new = [{"rule": "你应该先读盘再汇报", "source": "distilled"}]
    merged, evicted = _merge_constraints(old, new, 5)
    rules = [c["rule"] for c in merged]
    assert "你不应该把探针失效读成事实" in rules
    assert "你应该先读盘再汇报" in rules
    assert evicted == []


def test_c3b_duplicate_rule_not_doubled():
    old = [{"rule": "你应该先读盘再汇报"}]
    new = [{"rule": "你应该先读盘再汇报"}]
    merged, _ = _merge_constraints(old, new, 5)
    assert len(merged) == 1, merged


def test_c3c_overflow_evicts_newest_and_reports():
    """负控：超限时不许静默丢——被挤掉的必须回传。"""
    old = [{"rule": f"旧{i}"} for i in range(5)]
    new = [{"rule": "新规则A"}, {"rule": "新规则B"}]
    merged, evicted = _merge_constraints(old, new, 5)
    assert len(merged) == 5
    assert [c["rule"] for c in merged] == [f"旧{i}" for i in range(5)]
    assert evicted == ["新规则A", "新规则B"], evicted


def test_c3d_old_entries_fill_then_new_takes_free_slot():
    old = [{"rule": f"旧{i}"} for i in range(4)]
    new = [{"rule": "新规则A"}]
    merged, evicted = _merge_constraints(old, new, 5)
    assert len(merged) == 5 and evicted == []
    assert merged[-1]["rule"] == "新规则A"


def test_c3e_empty_new_keeps_all_old():
    """旧行为是 new 为空就整表 pop ⇒ 本用例是那条缺陷的回归闸。"""
    old = [{"rule": "必须保留的防护"}]
    merged, _ = _merge_constraints(old, [], 5)
    assert [c["rule"] for c in merged] == ["必须保留的防护"]


# ── 提示词取数面：旧约束必须喂给 LLM ───────────────────────────────


def test_fmt_includes_existing_constraints():
    data = {"memory": {
        "key_decisions": [], "learned_patterns": [],
        "behavioral_constraints": [{"rule": "你不应该空口弃权"}],
    }}
    text = _format_memory_for_distillation(data)
    assert "你不应该空口弃权" in text, text
