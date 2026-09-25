"""复读篇 P0（2026-09-26）——「跨轮复读」守卫：natural 出口不得回捞上一轮已投递的回复。

现场（盘上实证 · data/delivery_ledger.jsonl）：
  05:09:01 / 05:12:14 / 05:13:30 三次投递 **同 sha1=2bff1123ddf7**（741 字符），
  而三次 run 的输入分别是 2 / 9 / 21 字符、prompt 各差数倍 ⇒ 不可能同源生成。
  三次 run 全部 `reason=natural`、`has_written=False`、无任何 guard 拦截记录；
  第 3 个 run 仅 1 轮却烧 20.1s ⇒ 模型产出了思考内容、**最终正文为空**。

根因：`agent_loop` 把「无工具调用 + 空正文」当正常说完 ⇒ `natural` 退出 ⇒ `core_loop` 的
`reversed(messages)` 跨轮回捞到上一轮**已投递过**的回复原样重发。

判据锚**行为契约**（不锚字面量）：`exit_reason=natural` 且本轮正文为空 ⇒ 投出内容
**必须 ≠ 上一轮 assistant 内容**，且文案不得谎称「没调到模型」（那是 provider 侧假故障）。

实现方式（防「测的是转述不是生产代码」）：从盘上 `agent/core_loop.py` 抽取**真实判据块**
（`_final_content = ""` → `if _result.interrupted:` 之前）再 `exec`，不复制分支代码。
负控臂 = **修复前形态冻结件**（同一块去掉 final_content 透传分支），两臂只差该分支。

六臂：
  A 负控（冻结病形态）自然退出+空正文 ⇒ **复读上一轮**（病可复现，不是散文）
  B 新形态（盘上真源）同输入 ⇒ 明示，且 ≠ 上一轮
  C 孪生 natural + 真正文 ⇒ 原样返回（防「一刀切明示」把正常路径打红）
  D `empty_content` ⇒ 明示，且**不含**「没调到模型」（文案契约）
  E 兼容：natural 且**未透传** final_content（老调用方）⇒ 保持原检索语义（不回归）
  F 接线守卫：agent_loop 真 raise empty_content / 真透传 final_content；cron_mixin 记异常
"""
from __future__ import annotations

import pathlib
import textwrap

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
CORE = REPO_ROOT / "agent" / "core_loop.py"
AGENT_LOOP = REPO_ROOT / "agent" / "agent_loop.py"
CRON = REPO_ROOT / "gateway" / "cron_mixin.py"

_START = '_final_content = ""'
_END = "if _result.interrupted:"

PREV = "上一轮已投递过的旧回复（不该被重发）"
DECLARED = "本轮自己的新答案"
EMPTY = ""

MESSAGES = [
    {"role": "user", "content": "状态"},
    {"role": "assistant", "content": PREV},
    {"role": "user", "content": "状态"},
    {"role": "assistant", "content": EMPTY},  # 本轮：模型交白卷
]

# 修复前形态冻结件（2026-09-26 抽取 · natural 无条件回捞）——「病可复现」的活证据。
_FROZEN_LESION = (
    '_final_content = ""\n'
    'if (getattr(_result, "interrupted", False)):\n'
    '    for _md in reversed(_result.messages):\n'
    '        if _md.get("role") == "assistant" and _md.get("content"):\n'
    '            _final_content = _md.get("content", "")\n'
    '            break\n'
    'elif getattr(_result, "exit_reason", "") == "natural":\n'
    '    for _md in reversed(_result.messages):\n'
    '        if _md.get("role") == "assistant" and _md.get("content"):\n'
    '            _final_content = _md.get("content", "")\n'
    '            break\n'
    'else:\n'
    '    _final_content = "[故障明示] 兜底"\n'
)


class _Logger:
    def __init__(self) -> None:
        self.errors: list[tuple] = []

    def error(self, *a, **k) -> None:  # noqa: D102
        self.errors.append(a)


_UNSET = object()


class _Result:
    def __init__(self, exit_reason: str, messages: list, final_content=_UNSET):
        self.exit_reason = exit_reason
        self.interrupted = False
        self.messages = messages
        self.turns_used = 1
        if final_content is not _UNSET:
            self.final_content = final_content


def _extract_block(src: str) -> str:
    lines = src.splitlines(keepends=True)
    start = next((i for i, ln in enumerate(lines) if ln.strip() == _START), None)
    assert start is not None, f"锚点丢失：{_START!r} 不在 {CORE}"
    end = next((i for i, ln in enumerate(lines[start:], start) if ln.strip().startswith(_END)), None)
    assert end is not None, f"锚点丢失：{_END!r} 不在 {CORE}"
    block = "".join(lines[start:end])
    # 锚点漂移守卫：必须含 natural / empty_content / fail-closed 三处结构标记
    for marker in ('"natural"', '"empty_content"', "fail-closed"):
        assert marker in block, f"抽到的块不含 {marker}——锚点漂了"
    return textwrap.dedent(block)


def _run(block: str, result: _Result):
    lg = _Logger()
    ns = {"_result": result, "logger": lg, "task_id": "replay000", "getattr": getattr}
    exec(compile(textwrap.dedent(block), "<core_loop.py:natural-branch>", "exec"), ns)
    return ns["_final_content"], lg


def _live() -> str:
    return _extract_block(CORE.read_text(encoding="utf-8"))


# ── 臂 A：负控（冻结病形态）⇒ 复读上一轮 ─────────────────────────────────────
def test_armA_frozen_lesion_replays_previous_turn():
    content, _ = _run(_FROZEN_LESION, _Result("natural", MESSAGES))
    assert content == PREV, f"冻结病形态应当复读上一轮，实得 {content[:60]!r}"


# ── 臂 B：新形态 ⇒ 空正文不再回捞 ────────────────────────────────────────────
def test_armB_live_blank_content_does_not_replay_previous_turn():
    content, lg = _run(_live(), _Result("natural", MESSAGES, final_content=""))
    assert content != PREV, "空正文仍复读上一轮 = P0 未修"
    assert "故障明示" in content and "空正文" in content, f"应为空正文明示，实得 {content[:80]!r}"
    assert lg.errors, "明示分支必须留 error 级日志（否则无人知道发生过）"


# ── 臂 C：孪生（真正文）⇒ 原样返回，正常路径不得被打红 ────────────────────────
def test_armC_twin_real_content_returned_as_is():
    content, lg = _run(_live(), _Result("natural", MESSAGES, final_content=DECLARED))
    assert content == DECLARED, f"normal 正常回复被改写：{content[:60]!r}"
    assert not lg.errors, "正常路径不得产生 error 日志"


# ── 臂 D：empty_content ⇒ 明示 + 文案契约（不得谎称没调到模型） ──────────────
def test_armD_empty_content_explicit_and_text_contract():
    content, lg = _run(_live(), _Result("empty_content", MESSAGES, final_content=""))
    assert content != PREV, "empty_content 仍复读上一轮"
    assert "empty_content" in content, "文案须携带原样 reason（供 Q6 投递对账归因）"
    assert "没调到模型" not in content, "模型调到了（只是交白卷）——不得引向 provider 侧假故障"
    assert lg.errors


# ── 臂 E：兼容（未透传 final_content 的老调用方）⇒ 语义不变 ─────────────────
def test_armE_legacy_caller_without_declared_content_unchanged():
    content, _ = _run(_live(), _Result("natural", MESSAGES))
    assert content == PREV, "未透传时应保持原检索语义（兼容路径不得被本单改动影响）"


# ── 臂 F：接线守卫（防「助手存在但没人调」复发） ─────────────────────────────
def test_armF_wiring_guards():
    al = AGENT_LOOP.read_text(encoding="utf-8")
    assert 'AgentLoopExit("empty_content"' in al, "agent_loop 未在空正文路径改判 empty_content"
    assert '"final_content": content or ""' in al, "natural 退出未透传 final_content"
    cm = CRON.read_text(encoding="utf-8")
    assert '"empty_content"' in cm, "cron_mixin 未把 empty_content 计入异常退出（台账会记 ok = 假绿）"


# ── 臂 G：行为级端到端（真跑 MimirAgentLoop，非字符串断言） ────────────────────
# 这是本单最强的一条：用**真循环**驱动一个「思考有、正文空」的假模型，
# 断言 exit_reason 改判 empty_content 且 final_content 为空（不再 natural + 复读）。
_REAL_CONTENT = "本轮真正的答复（孪生用）"


def _drive(blank: bool):
    import asyncio
    import sys

    sys.path.insert(0, str(REPO_ROOT))
    from agent.agent_loop import MimirAgentLoop  # noqa: PLC0415

    payload = (
        {"choices": [{"message": {"content": "", "tool_calls": None,
                                  "reasoning_content": "思考内容有、最终正文空"}}]}
        if blank
        else {"choices": [{"message": {"content": _REAL_CONTENT, "tool_calls": None,
                                       "reasoning_content": "x"}}]}
    )

    async def _model_call(_msgs):
        return payload

    loop = MimirAgentLoop(
        model_call=_model_call,
        tool_schemas=[],
        valid_tool_names=set(),
        tool_dispatcher=lambda *a, **k: "",
        max_turns=9,
        task_id="replaybeh",
    )
    msgs = [
        {"role": "user", "content": "状态"},
        {"role": "assistant", "content": PREV},
        {"role": "user", "content": "状态"},
    ]
    return asyncio.run(loop.run(msgs))


def test_armG_behavior_blank_reply_never_exits_as_natural():
    res = _drive(blank=True)
    assert getattr(res, "exit_reason", "") == "empty_content", (
        f"空正文仍以 {getattr(res, 'exit_reason', None)!r} 退出 = 会触发跨轮复读"
    )
    assert getattr(res, "final_content", None) == "", "空正文必须透传空串（不得塞入旧回复）"


def test_armG2_behavior_real_reply_still_natural_twin():
    res = _drive(blank=False)
    assert getattr(res, "exit_reason", "") == "natural", (
        f"正常回复被改判 {getattr(res, 'exit_reason', None)!r} = 孪生臂被打红"
    )
    assert getattr(res, "final_content", "") == _REAL_CONTENT
