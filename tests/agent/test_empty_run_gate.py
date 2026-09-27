"""空跑闸门回归用例（2026-09-28 · 第 3 次空跑实证后的根治线）。

## 被测对象
`agent/empty_run_gate.py` + `agent/agent_loop.py` 的四处接线。

## 病灶（盘上取证）
- run be1eb421e3a066cf（2026-09-27T19:48:24→19:49:53 · 89.75s · 10 步）：
  10/10 只读、0 写交付物、空正文退出（exit_reason=empty_content）⇒ 任务书五问一句没答。
- run d85a4c1097d19fb4（第 2 次 · 8 步）：执行了 1 次 execute_code 写**中转草稿**
  （tmp/b2/src.md），此后 7 步只读，交付物未写 ⇒ 同样空跑；而 has_written 读成 False
  （WRITE_TOOLS 只认 write_file/patch ⇒ execute_code 写盘不计）= 量具缺口。

## 本用例的「回归」含义（防复发，不是防回归）
**模拟只读多的任务 → 断言有产出**：
  臂 D 用真 `MimirAgentLoop` 驱动「1 次写中转草稿 + N 次只读 + 空正文收尾」的假模型，
  断言退出时**盘上有交付物**（草稿被 flush 成半段卡）。臂 E 为负控（闸门关 ⇒ 无产物），
  证明「产物是闸门产生的」而不是别处顺手写的。

## 臂清单
  A 分类纯函数：execute_code 内容级判定（写/读）
  B 只读连续计数：写轮清零、无工具轮不打断
  C tick 触发：达限且未写交付物 ⇒ 返回硬指令；已写 ⇒ None
  D flush 幂等：草稿落成半段卡、重复调用不重复追加
  E 回归（行为级）：只读多的任务 ⇒ 有产出（真跑 loop）
  F 负控：MIMIR_EMPTY_RUN_GATE=0 ⇒ 无产物（证因果）
  G 接线守卫：agent_loop 真有 tick/flush 两个钩子
"""
from __future__ import annotations

import asyncio
import json
import logging
import pathlib
import re
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from agent import empty_run_gate as erg  # noqa: E402
from agent.agent_loop import MimirAgentLoop  # noqa: E402

CARD_PREFIX = "EMPTYRUN_CARD"
DRAFT_BODY = "半段骨架：五问立场 1-5（staging 草稿·flush 前）"


def _tc(name, args):
    return {"id": "call_" + name, "type": "function",
            "function": {"name": name, "arguments": json.dumps(args)}}


def _read_args(path):
    return {"code": "print(open(" + repr(str(path)) + ").read())"}


def _write_args(path):
    return {"code": "open(" + repr(str(path)) + ", 'w').write('x')"}


def _msgs(turns, card_path):
    out = [{"role": "user", "content": "任务书：请回复五问。目标卡 " + str(card_path)}]
    for kind, path in turns:
        name = "execute_code" if kind != "tool" else "write_file"
        args = _read_args(path) if kind == "read" else _write_args(path)
        out.append({"role": "assistant", "content": "",
                    "tool_calls": [_tc(name, args)]})
        out.append({"role": "tool", "tool_call_id": "call_" + name, "content": "ok"})
    return out


# ── 臂 A：分类纯函数 ──────────────────────────────────────────────────
def test_armA_classify_execute_code_content_level(tmp_path):
    p = tmp_path / "x.md"
    assert erg.classify_tool("execute_code", json.dumps(_read_args(p))) == "readonly"
    assert erg.classify_tool("execute_code", json.dumps(_write_args(p))) == "write"
    assert erg.classify_tool("read_file") == "readonly"
    assert erg.classify_tool("write_file") == "write"
    assert erg.turn_kind(["read_file"]) == "readonly"
    assert erg.turn_kind(["read_file", "write_file"]) == "write"
    assert erg.turn_kind([]) == "none"


# ── 臂 B：只读连续计数 ────────────────────────────────────────────────
def test_armB_readonly_streak_counts_and_resets(tmp_path):
    card = tmp_path / (CARD_PREFIX + "_B.md")
    turns = [("read", tmp_path / "a.md")] * 5
    assert erg.readonly_streak(_msgs(turns, card)) == 5
    turns = [("read", tmp_path / "a.md")] * 3 + [("write", tmp_path / "b.md")] + [("read", tmp_path / "c.md")] * 2
    assert erg.readonly_streak(_msgs(turns, card)) == 2, "写轮应清零预算（只数其后的只读轮）"
    msgs = _msgs([("read", tmp_path / "a.md")], card)
    msgs.append({"role": "assistant", "content": "我在说话（无工具）"})
    assert erg.readonly_streak(msgs) == 1, "无工具调用的 assistant 轮不得打断计数"


# ── 臂 C：tick 触发 ───────────────────────────────────────────────────
def test_armC_tick_returns_directive_and_skips_when_written(tmp_path):
    card = tmp_path / (CARD_PREFIX + "_C.md")
    msgs = _msgs([("read", tmp_path / "a.md")] * 5, card)
    gate = erg.EmptyRunGate(task_id="armC", limit=4, force_writes=1)
    d = gate.tick(msgs, 5)
    assert isinstance(d, str) and "写" in d and "空跑闸门" in d, d
    assert gate.streak >= 4
    msgs.append({"role": "assistant", "content": "",
                 "tool_calls": [_tc("write_file", {"path": str(card), "content": "x"})]})
    assert gate.tick(msgs, 6) is None, "已写交付物 ⇒ 不得再拦"


# ── 臂 D：flush 幂等 ──────────────────────────────────────────────────
def test_armD_flush_draft_is_idempotent(tmp_path):
    draft = tmp_path / "staging" / "draft.md"
    draft.parent.mkdir(parents=True, exist_ok=True)
    draft.write_text(DRAFT_BODY, encoding="utf-8")
    card = tmp_path / (CARD_PREFIX + "_D.md")
    card.write_text("原有卡头\n", encoding="utf-8")
    r1 = erg.flush_draft(str(draft), str(card), "armD", 3, "empty_content")
    assert r1["flushed"] is True and r1["target"] == str(card)
    t1 = card.read_text(encoding="utf-8")
    assert DRAFT_BODY in t1 and erg.HALF_MARK in t1 and "原有卡头" in t1
    r2 = erg.flush_draft(str(draft), str(card), "armD", 4, "empty_content")
    assert r2["flushed"] is False and r2["reason"] == "already_flushed"
    assert card.read_text(encoding="utf-8").count(erg.HALF_MARK) == 1, "重复 flush 不得重复追加"


# ── 臂 E/F 的行为级驱动（真跑 MimirAgentLoop · 非字符串断言）────────────
def _drive(tmp_path, readonly_turns, gate_on):
    """假模型：1 轮写**中转草稿**（staging）+ N 轮只读 + 最后空正文收尾。

    这正是 run be1eb421 / d85a4c10 的盘上形态（读齐材料 → 不落交付物 → 空正文退出）。
    """
    draft = tmp_path / "staging" / "draft.md"
    draft.parent.mkdir(parents=True, exist_ok=True)
    card = tmp_path / (CARD_PREFIX + "_E.md")
    pattern = str(tmp_path).replace(".", "[.]") + "/" + CARD_PREFIX + "_[A-Za-z0-9]+[.]md"
    old_hints = erg._CARD_HINTS
    erg._CARD_HINTS = re.compile(pattern)   # 只换「哪条路径算目标卡」，不换机制
    state = {"n": 0}

    def dispatcher(name, args, tid):
        draft.parent.mkdir(parents=True, exist_ok=True)
        draft.write_text(DRAFT_BODY, encoding="utf-8")
        return "ok"

    async def model_call(msgs):
        state["n"] += 1
        if state["n"] == 1:
            tc = [_tc("execute_code", _write_args(draft))]
        elif state["n"] <= 1 + readonly_turns:
            tc = [_tc("execute_code", _read_args(draft))]
        else:
            tc = None
        return {"choices": [{"message": {"content": "", "tool_calls": tc,
                                         "reasoning_content": "思考有·正文空"}}]}

    loop = MimirAgentLoop(
        model_call=model_call,
        tool_schemas=[{"type": "function",
                       "function": {"name": "execute_code",
                                    "parameters": {"type": "object", "properties": {}}}}],
        valid_tool_names={"execute_code"},
        tool_dispatcher=dispatcher,
        max_turns=20,
        task_id="emptygateE",
    )
    msgs = [{"role": "user", "content": "任务书：五问待拍。目标卡 " + str(card)}]
    try:
        res = asyncio.run(loop.run(msgs))
    finally:
        erg._CARD_HINTS = old_hints
    return res, card, draft


def test_armE_regression_readonly_heavy_task_has_artifact(tmp_path, monkeypatch, caplog):
    """回归主臂：只读多的任务 ⇒ **必须有产出**（草稿 flush 成半段卡）。"""
    monkeypatch.setenv("MIMIR_EMPTY_RUN_GATE", "1")
    monkeypatch.setenv("MIMIR_READONLY_TURN_LIMIT", "4")
    monkeypatch.setenv("MIMIR_EMPTY_RUN_MAX_FORCE", "1")
    # 隔离本臂：关掉 verify 闸 / TD-03 硬拦截链，使流程**确定性**走到 empty_content 出口
    # （本臂测的是空跑闸门；那条链已由 test_cross_turn_replay_guard 覆盖）
    monkeypatch.setenv("MIMIR_VERIFY_BEFORE_REPORT", "0")
    monkeypatch.setenv("MIMIR_PRODUCTION_ENFORCE", "0")
    with caplog.at_level(logging.WARNING):
        res, card, draft = _drive(tmp_path, readonly_turns=6, gate_on=True)
    assert getattr(res, "exit_reason", "") == "empty_content", (
        "空正文仍须显式记为 empty_content（不得装 normal）—— 实得 "
        + repr(getattr(res, "exit_reason", None)))
    assert card.exists(), "只读多的任务必须留下产出（否则=同类空跑复发）"
    txt = card.read_text(encoding="utf-8")
    assert DRAFT_BODY in txt, "交付物必须含已读材料（草稿内容）"
    assert erg.HALF_MARK in txt, "必须带半段标记（可续写、不谎称完工）"
    assert any("空跑闸门" in r.getMessage() for r in caplog.records), "闸门触发必须留 WARNING 日志"


def test_armF_negative_control_gate_off_no_artifact(tmp_path, monkeypatch):
    """负控：闸门关 ⇒ 同样的任务**无产物**（证明产物是闸门产生的，不是别处顺手写的）。"""
    monkeypatch.setenv("MIMIR_EMPTY_RUN_GATE", "0")
    res, card, draft = _drive(tmp_path, readonly_turns=6, gate_on=False)
    assert getattr(res, "exit_reason", "") == "empty_content"
    assert not card.exists(), "闸门关时不该有产物——若有，说明臂 E 的断言不是闸门的功劳"


def test_armE2_guards_on_still_leaves_artifact(tmp_path, monkeypatch):
    """孪生臂：**不关任何闸门**（verify/TD-03 全默认开）⇒ 退出原因可能是 verify_exhausted，
    但不变式必须成立：①不得装 natural ②盘上必须有产出。"""
    monkeypatch.setenv("MIMIR_EMPTY_RUN_GATE", "1")
    monkeypatch.setenv("MIMIR_READONLY_TURN_LIMIT", "4")
    monkeypatch.setenv("MIMIR_EMPTY_RUN_MAX_FORCE", "0")
    for k in ("MIMIR_VERIFY_BEFORE_REPORT", "MIMIR_PRODUCTION_ENFORCE"):
        monkeypatch.delenv(k, raising=False)
    res, card, draft = _drive(tmp_path, readonly_turns=6, gate_on=True)
    reason = getattr(res, "exit_reason", "")
    assert reason and reason != "natural", "空正文/无产出不得以 natural 退出（实得 " + repr(reason) + "）"
    assert card.exists(), "任何失败出口都必须留下产出（这是本闸门的核心不变式）"
    assert DRAFT_BODY in card.read_text(encoding="utf-8")


# ── 臂 G：接线守卫（防「函数存在但没人调」）──────────────────────────────
def test_armG_wiring_hooks_present():
    al = (REPO / "agent" / "agent_loop.py").read_text(encoding="utf-8")
    for marker in (
        "_empty_run_gate_mod()",          # 惰性导入
        "空跑闸门 B",                      # 只读预算硬限（每轮 tick）
        "_erg.tick(messages, turn + 1)",  # 真调用
        "空跑闸门 A",                      # exit 前 flush
        "_empty_run_gate_pre_exit",       # 真调用（定义 + 2 处出口）
        "self._empty_run_flushed_paths",  # 量具：flush 计入 has_written
    ):
        assert marker in al, "接线缺失：" + marker
    assert al.count("_empty_run_gate_pre_exit") >= 3, "应至少 1 处定义 + 2 处调用（empty_content / _finalize_exit）"
    assert 'AgentLoopExit("empty_content"' in al, "empty_content 出口不得被删除（闸门只加不删）"
