"""A2（2026-09-24 四方共识）twin-arm：core_loop 最终内容判定 fail-closed 反转的负控四臂。

旧形态=「白名单内明示+其余 reversed() 复读」⇒ 未知 reason 默认复读旧回复（fail-open）。
新形态=「仅 natural/interrupted 取当前回复+其余一切明示」（fail-closed）。
"""
import re
from pathlib import Path

_SRC = (Path(__file__).resolve().parents[2] / "agent" / "core_loop.py").read_text(encoding="utf-8")


def _final_block():
    m = re.search(r"A2（2026-09-24 四方共识.*?(?=\n            if _result\.interrupted:)", _SRC, re.S)
    assert m, "A2 判定块必须可定位"
    return m.group(0)


def test_arm_a_fail_closed_structure():
    """臂 A：判定顺序=natural 显式分支在前+兜底 else=明示（fail-closed 结构钉死）。"""
    blk = _final_block()
    assert 'elif _exit_reason == "natural":' in blk
    assert blk.rstrip().endswith('_exit_reason, task_id[:8])') or "明示故障状态" in blk.split("else:")[-1]
    # 兜底分支必须是明示，不是复读
    tail = blk.split("else:")[-1]
    assert "[故障明示]" in tail and "reversed(" not in tail, "兜底 else 必须明示而非复读"


def test_arm_b_unknown_reason_shows_fault():
    """臂 B（核心负控）：未知 reason（brand_new_reason）走明示文案——旧形态这里会复读。"""
    blk = _final_block()
    # 未知 reason 只能落 else：natural/billing/max_turns 均为 == 精确比较，无集合 in 判定
    assert '_ABNORMAL_EXIT_REASONS' not in blk, "白名单集合判定必须已死（fail-open 源头）"
    assert 'brand_new_reason' not in blk  # 不特判即可——落兜底
    assert "不会伪装成正常回复" in blk


def test_arm_c_natural_takes_current_reply():
    """臂 C（孪生）：natural ⇒ reversed 取当前回复（复读路径仅存于此分支）。"""
    blk = _final_block()
    natural_branch = blk.split('elif _exit_reason == "natural":')[1].split("elif")[0]
    assert "reversed(" in natural_branch
    # reversed 复读代码只允许出现 2 次（interrupted + natural）——注释行不计
    code_lines = [ln for ln in blk.splitlines() if not ln.strip().startswith("#")]
    n = sum(ln.count("reversed(") for ln in code_lines)
    assert n == 2, f"复读面必须锁死在 natural/interrupted 两分支（实测 {n} 处代码调用）"


def test_arm_d_special_texts_preserved():
    """臂 D：billing 断粮文案与 max_turns 到顶文案逐字保留（诊断价值不回退）。"""
    blk = _final_block()
    assert "[断粮] provider 额度耗尽（402/billing）" in blk
    assert "[故障明示] 轮次预算用尽（reason=max_turns" in blk
