"""A1（2026-09-24 卡 §15 · 实施轮）—— `max_turns` 走「明示」而非复读最后一条 assistant。

判据锚**行为契约**（卡 §14.4 A1 细化①）：**不**断言 `"max_turns" in _ABNORMAL_EXIT_REASONS`
（A2 会废除该白名单 ⇒ 锚字面量的断言在 A2 落地时必被改写成假绿），
而是断言 `exit_reason=max_turns` ⇒ 投出文案 **≠ 最后一条 assistant content**。

实现方式（防「测的是转述不是生产代码」）：**不复制**分支代码，而是从盘上
`agent/core_loop.py` 里**抽取真实判据块**（`_final_content = ""` → `if _result.interrupted:`
之前）再 `exec`。

受控差分：负控臂 = **同一块删掉 `max_turns` 一个 token**（不是手抄旧版），
⇒ 两臂只差一个 token，差异即该 token 的因果。

四臂（卡 §14.4 A1 细化② 的 `and not interrupted` 守卫两臂 + 单子孪生）+ 一条同块回归：
  A 负控（旧形态·删 token）  ⇒ 复读末条 assistant（病可复现，不是散文）
  B 新形态（盘上真源）        ⇒ 明示，且 ≠ 末条 assistant
  C 孪生 `natural`            ⇒ 仍返回当前回复（防「一刀切明示」把正常路径打红）
  D `max_turns + interrupted=True` ⇒ **不**被明示覆盖（走既有 `if _result.interrupted:` 早退）
  E `billing_exhausted`       ⇒ 同块未受影响（回归）

**刻意锁死的文案契约**（本单的 ±偏离，卡 §15 已申报）：
max_turns 的明示**不得**谎称「没调到模型」——它是「调到了模型但轮次用尽」。
⇒ 断言明示文案不含 `没调到模型`、且携带原样 `reason=max_turns`（供 Q6 投递对账按串归因）。
"""
from __future__ import annotations

import pathlib
import textwrap

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
SRC_PATH = REPO_ROOT / "agent" / "core_loop.py"

_START = '_final_content = ""'
_END = "if _result.interrupted:"
_TOKEN = ', "max_turns"'

# 末条 assistant = 「未收尾的半句/计划复述」形态（卡 §1.2 现场：17 步停在「Now Phase 1」将来时）
TAIL_ASSISTANT = "本轮读剩余 5 个文件全文："
EARLIER_ASSISTANT = "上一轮的旧回复（不该被当成最终答复）"

MESSAGES = [
    {"role": "user", "content": "干活"},
    {"role": "assistant", "content": EARLIER_ASSISTANT},
    {"role": "tool", "content": "tool output"},
    {"role": "user", "content": "继续"},
    {"role": "assistant", "content": TAIL_ASSISTANT},
]


class _Logger:
    def __init__(self) -> None:
        self.errors: list[tuple] = []

    def error(self, *a, **k):  # noqa: D102
        self.errors.append(a)


class _Result:
    def __init__(self, exit_reason: str, interrupted: bool, messages: list, turns_used: int = 90):
        self.exit_reason = exit_reason
        self.interrupted = interrupted
        self.messages = messages
        self.turns_used = turns_used


def _extract_branch(src: str) -> str:
    """抽取盘上真实判据块（`_ABNORMAL_EXIT_REASONS` 白名单 + if/else 复读分支）。"""
    lines = src.splitlines(keepends=True)
    start = next((i for i, ln in enumerate(lines) if ln.strip() == _START), None)
    assert start is not None, f"锚点丢失：{_START!r} 不在 {SRC_PATH}"
    end = next(
        (i for i, ln in enumerate(lines[start:], start) if ln.strip().startswith(_END)), None
    )
    assert end is not None, f"锚点丢失：{_END!r} 不在 {SRC_PATH}"
    block = "".join(lines[start:end])
    # A2 适配（2026-09-24）：白名单已废（fail-closed 反转）——锚新结构标记
    assert '"natural"' in block and "fail-closed" in block, "抽到的块不含 A2 fail-closed 判定——锚点漂了"
    assert "reversed(_result.messages)" in block, "抽到的块不含取当前回复分支——锚点漂了"
    return textwrap.dedent(block)


def _strip_max_turns(block: str) -> tuple[str, int]:
    """受控差分：负控臂 = 同一块删掉 `max_turns` 一个 token。"""
    return block.replace(_TOKEN, ""), block.count(_TOKEN)


def _run(block: str, exit_reason: str, interrupted: bool, messages: list):
    block = textwrap.dedent(block)  # 冻结件内嵌字符串自带缩进——exec 前归一
    lg = _Logger()
    ns = {
        "_result": _Result(exit_reason, interrupted, messages),
        "logger": lg,
        "task_id": "a1max0000",
        "getattr": getattr,
    }
    exec(compile(block, "<core_loop.py:1054-branch>", "exec"), ns)
    return ns["_final_content"], lg


def _live_block() -> str:
    return _extract_branch(SRC_PATH.read_text(encoding="utf-8"))


# A2 适配（2026-09-24）：A2 废白名单后「删 token」负控构造失效——臂 A 重锚为
# **8-25 病形态冻结块**（d95d7fc~1 抽取·max_turns 不在名单·exec 原样跑）。
# 冻结件纪律（A3 §五）：要验的形态不复存在时先冻下来——这块就是「修复前」的活证据。
_FROZEN_LESION_825 = '_final_content = ""\n_ABNORMAL_EXIT_REASONS = {"api_failure", "empty_response", "format_error", "no_choices", "billing_exhausted"}\nif (getattr(_result, "exit_reason", "") in _ABNORMAL_EXIT_REASONS\n        and not getattr(_result, "interrupted", False)):\n    # 断粮单独文案（体检复核 M-2 补修·Mimir 建议）：402/额度耗尽与笼统故障区分，\n    # 保住 9-21 案例的诊断价值（否则billing_exhausted 只会收到笼统"故障明示"）。\n    if getattr(_result, "exit_reason", "") == "billing_exhausted":\n        _final_content = "[断粮] provider 额度耗尽（402/billing），本轮未调用模型——请充值或切换凭证后重试；不会重发旧回复伪装正常"\n        logger.error("[%s] [EXIT] billing_exhausted：断粮明示，不重发旧回复", task_id[:8])\n    else:\n        _final_content = "[故障明示] 我这轮没调到模型（连续错误），请让我重启或查看日志——故障已记录，不会伪装成正常回复"\n        logger.error("[%s] [EXIT] 异常退出 %s：不重发旧回复，明示故障状态", task_id[:8], _result.exit_reason)\nelse:\n    for _md in reversed(_result.messages):\n        if _md.get("role") == "assistant" and _md.get("content"):\n            _final_content = _md.get("content", "")\n            break\n'


# ── 臂 A：负控（8-25 病形态冻结件）⇒ 复读，病可复现 ────────────────────────────
def test_armA_legacy_form_replays_tail_assistant():
    old_block = _FROZEN_LESION_825
    assert "_ABNORMAL_EXIT_REASONS" in old_block and ', "max_turns"' not in old_block, (
        "冻结件必须是 max_turns 不在名单的 8-25 病形态"
    )
    content, lg = _run(old_block, "max_turns", False, MESSAGES)
    assert content == TAIL_ASSISTANT, "旧形态应复读末条 assistant（这就是本单要修的病）"
    assert not lg.errors, "旧形态不该走明示分支"


# ── 臂 B：新形态（盘上真源）⇒ 明示，且 ≠ 末条 assistant ───────────────────────
def test_armB_max_turns_emits_fault_notice_not_replay():
    content, lg = _run(_live_block(), "max_turns", False, MESSAGES)
    assert content != TAIL_ASSISTANT, "行为契约：max_turns ⇒ 投出文案 ≠ 上一条 assistant content"
    assert content != EARLIER_ASSISTANT, "也不得复读更早的旧回复"
    assert content.startswith("[故障明示]"), "须留在既有三互斥前缀内（不新造第 4 前缀）"
    assert "不重发旧回复" in content
    assert "reason=max_turns" in content, "原样 reason 须可 grep（Q6 投递对账按串归因）"
    assert "没调到模型" not in content, (
        "文案失真守卫：max_turns 是「调到了模型但轮次用尽」，不得谎称 API/连续错误"
    )
    assert lg.errors, "明示必须留日志（零新增埋点：复用现有 logger.error）"


# ── 臂 C：孪生 natural ⇒ 仍返回当前回复（不误伤正常路径）─────────────────────
def test_armC_twin_natural_still_returns_current_reply():
    content, lg = _run(_live_block(), "natural", False, MESSAGES)
    assert content == TAIL_ASSISTANT
    assert not content.startswith("[故障明示]")
    assert not lg.errors


# ── 臂 D：max_turns + interrupted=True ⇒ 不被明示覆盖 ─────────────────────────
def test_armD_interrupted_not_overridden_by_notice():
    content, lg = _run(_live_block(), "max_turns", True, MESSAGES)
    assert not content.startswith("[故障明示]"), "`and not interrupted` 守卫：中断臂不得被明示覆盖"
    assert not lg.errors
    src = SRC_PATH.read_text(encoding="utf-8")
    assert 'return f"对话已被中断。' in src, "既有中断早退通道（interrupt 分支）须仍在"


# ── 臂 E：billing_exhausted 未受影响（同块回归）──────────────────────────────
def test_armE_billing_branch_unchanged():
    content, lg = _run(_live_block(), "billing_exhausted", False, MESSAGES)
    assert content.startswith("[断粮]")
    assert lg.errors
