"""A1 漂移闸门（2026-10-04 · Mimir 角色审计 A1 整改）。

背景
----
H-1 修复（commit d913b5c）只补了 `search_first_guard._INJECTED_USER_PREFIXES` **一处**
⇒ 角色审计判 **A1 blocker = 单点修补**（违反自订「同类风险全量扫，禁单点修补」）。
实测：`agent_loop.py` 两处同语义清单仍缺中文【】族，行为面已复现
（`【空跑闸门】…` 在两处 skipped=False ⇒ 被当「真实用户消息」）。

本用例 = **机制**（不是再提醒一次）：把「同族清单必须互相覆盖」写成可跑闸门。
实证：本闸门在 2026-10-04 第一次运行时，**当场抓到修复补丁自身删掉了 "【架构" 的回归**。

权威参照：`agent/verify_before_report_guard.py` 的 `_SYSTEM_INJECT_PREFIXES`
（2026-09-29 全仓正则扫描 14 候选后的结论版，含 9 项中文族）。
"""

import pytest

from agent.agent_loop import MimirAgentLoop, _INTENT_SKIP_PREFIXES
from agent.search_first_guard import _INJECTED_USER_PREFIXES
from agent.verify_before_report_guard import _SYSTEM_INJECT_PREFIXES as VBG_PREFIXES

# 全族 4 份拷贝（2026-10-04 全仓扫描；intent_predictor.py:110 是**生产者**非跳过清单，已排除）
FAMILY = {
    "agent_loop._INTENT_SKIP_PREFIXES": _INTENT_SKIP_PREFIXES,
    "agent_loop.MimirAgentLoop._SYSTEM_INJECT_PREFIXES": MimirAgentLoop._SYSTEM_INJECT_PREFIXES,
    "search_first_guard._INJECTED_USER_PREFIXES": _INJECTED_USER_PREFIXES,
    "verify_before_report_guard._SYSTEM_INJECT_PREFIXES": VBG_PREFIXES,
}

# 生产端真实存在的中文方括号注入面（2026-09-29 全仓扫描结论）
REQUIRED_CJK = (
    "【架构",
    "【空跑闸门",
    "【读闸",
    "【任务完成度提示",
    "【自动唤醒",
    "【讨论室唤醒",
    "【任务】",
    "【审计统计】",
)


def _cjk(seq):
    return {p for p in seq if p.startswith("【")}


def _relates(prefixes, sample):
    """sample 与 prefixes 中某项是否**同族**。

    同族 = 互为前缀（允许简写形）：如 "【架构" 与 "【架构产出提示】" 视为同一族。
    """
    return any(sample.startswith(p) or p.startswith(sample) for p in prefixes)


@pytest.mark.parametrize("name", sorted(FAMILY))
def test_each_copy_covers_required_cjk_family(name):
    """每份拷贝都必须覆盖全部必需中文注入族（防漏项）。"""
    missing = [p for p in REQUIRED_CJK if not _relates(FAMILY[name], p)]
    assert not missing, f"{name} 缺中文注入族: {missing}"


def test_all_copies_mutually_cover_cjk_family():
    """漂移闸门：4 份拷贝的中文族必须**互相覆盖**（防单点修补复发）。

    实证价值：2026-10-04 首次运行即抓到「补丁把 "【架构" 删掉」的回归。
    """
    names = sorted(FAMILY)
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            ca, cb = _cjk(FAMILY[a]), _cjk(FAMILY[b])
            only_a = sorted(x for x in ca if not _relates(cb, x))
            only_b = sorted(x for x in cb if not _relates(ca, x))
            assert not only_a and not only_b, (
                f"{a} 与 {b} 中文族不同族：\n"
                f"  仅 {a} 有: {only_a}\n  仅 {b} 有: {only_b}"
            )


def test_intent_context_tag_present_in_all_copies():
    """`<intent-context>` 是 H-1 的原始病灶，必须仍在每份清单里。"""
    for name, seq in FAMILY.items():
        assert "<intent-context>" in seq, f"{name} 缺 <intent-context>"


def test_mimir_nudge_prefix_covered_in_all_copies():
    """`[MIMIR_PARALLEL_READ_NUDGE]` 等 `[MIMIR_` 族也是 user 角色注入 ⇒ 须被跳过。"""
    for name, seq in FAMILY.items():
        assert _relates(seq, "[MIMIR_PARALLEL_READ_NUDGE] "), f"{name} 未覆盖 [MIMIR_ 族"


def test_cjk_prefixes_do_not_swallow_plain_user_text():
    """负控：清单非恒真——普通中文用户消息不得被任何清单吞掉。"""
    for name, seq in FAMILY.items():
        assert not _relates(seq, "今天天气不错"), name
        assert not _relates(seq, "帮我看下 git 状态"), name


def test_behavioral_production_gate_correctly_classifies_cjk_injection():
    """行为面（非仅常量比对）：`_should_nudge_production` 必须把中文注入当「非真实消息」。

    受控差分（唯一变量=代码版本）：
      修复前：最末 msg 是【空跑闸门】注入 ⇒ 被当真实消息（长、非问句）⇒ 判「需产出」= True
      修复后：注入被跳过 ⇒ 取到真实短问句「帮我看下 git 状态」⇒ 判「无需产出」= False
    """
    loop = MimirAgentLoop.__new__(MimirAgentLoop)  # 不跑 __init__（避免重依赖）

    real = {"role": "user", "content": "帮我看下 git 状态"}
    inject = {
        "role": "user",
        "content": "【空跑闸门】本 run 已连续 4 轮只读（预算 4）且**交付物未写**——本轮必须先落盘再继续",
    }
    assert loop._should_nudge_production([real, inject]) is False

    # 正控：真实任务型消息仍必须判「需产出」（证明不是恒 False）
    task = {"role": "user", "content": "帮我把这份审计报告落盘到 notes/ 目录"}
    assert loop._should_nudge_production([task]) is True
