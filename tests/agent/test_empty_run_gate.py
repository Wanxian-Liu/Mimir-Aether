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
  B 未交付轮连续计数：非交付写不清零（P0-2）／交付物写清零／无工具轮不打断
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


# 交付物级路径（非 staging / 非工作记忆）——只作 tool args 用，无需真实存在。
_DELIVERABLE_CARD = "/repo/wiki/discussions/card_semantics.md"


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
    # P0-2（2026-10-07）语义变更：旧版「任意 write 清零」，新版「只有真写交付物清零」。
    # 判据：scripts/probes/empty_run_gate_budget_differential.py（旧版静默 4 轮 / 新版 0 轮）。
    staging = [("read", tmp_path / "a.md")] * 3 + [("write", tmp_path / "b.md")] + [("read", tmp_path / "c.md")] * 2
    assert erg.readonly_streak(_msgs(staging, card)) == 6, \
        "非交付写（tmp 草稿 = staging）**不得**退还预算——退还即旧版病灶（P0-2 已修）"
    real = [("read", tmp_path / "a.md")] * 3 + [("write", _DELIVERABLE_CARD)] + [("read", tmp_path / "c.md")] * 2
    assert erg.readonly_streak(_msgs(real, card)) == 2, "真写交付物应清零预算"
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
                 "tool_calls": [_tc("write_file", {"path": _DELIVERABLE_CARD, "content": "x"})]})
    assert gate.tick(msgs, 6) is None, "已写交付物 ⇒ 不得再拦"
    # 非交付写（staging）⇒ 拦截**不得**被解除（旧版在此被误读成「写过了」）
    msgs2 = _msgs([("read", tmp_path / "a.md")] * 5, card)
    msgs2.append({"role": "assistant", "content": "",
                  "tool_calls": [_tc("write_file", {"path": str(tmp_path / "s.md"), "content": "x"})]})
    gate2 = erg.EmptyRunGate(task_id="armC2", limit=4, force_writes=1)
    assert gate2.tick(msgs2, 6) is not None, "staging 写不得解除拦截（P0-2）"


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


# ═══════════════════════════════════════════════════════════════════════════
# P0-1 回归（2026-09-28 · probe_p5 5a 实证）：写动作 × 目标路径 **配对**
# 病灶：`_norm_paths()` 扫**整串 args** ⇒ 代码注释里「提及」的 *.log 被读成
#       交付物写入 ⇒ `deliverable_written()` 误真 ⇒ `tick()` 不注入 +
#       `flush()` 直接 `return []` ⇒ **B 段掩护被误关**（静默空跑，无掩护）。
# 判据：注释提及不影响判定；只有**写动作参数位**上的路径才算写目标。
# ═══════════════════════════════════════════════════════════════════════════
import json as _json  # noqa: E402
import os as _os  # noqa: E402

_H = _os.path.expanduser("~")
_MIMIR = _H + "/.mimiraether"
_WIKI = _H + "/wiki"



def _p01_ec(i, body):
    return {"role": "assistant", "content": "", "tool_calls": [
        {"id": "e%d" % i, "type": "function",
         "function": {"name": "execute_code", "arguments": _json.dumps({"code": body})}}]}


def test_p0_1_comment_mention_is_not_a_deliverable_write(tmp_path):
    """5a 型：写 staging 草稿 + 注释里提及 *.log ⇒ 不得判「写了交付物」。"""
    from agent import empty_run_gate as g
    draft = tmp_path / "b2" / "src.md"
    draft.parent.mkdir(parents=True, exist_ok=True)
    draft.write_text("draft", encoding="utf-8")
    log = _MIMIR + "/logs/agent.log"
    tc = _p01_ec(10, "open(%r,'a').write('x')  # log=%s" % (str(draft), log))
    msgs = [{"role": "user", "content": "任务：讨论 wiki/discussions/x.md"}, tc]
    assert g.deliverable_written(msgs) is False
    # 配对：只取 open() 的**目标位**（草稿），注释里的 .log 不算
    assert g.write_targets("execute_code", tc["tool_calls"][0]["function"]["arguments"]) == [str(draft)]


def test_p0_1_work_memory_keys_cover_logs():
    """运行日志/JSONL 不是交付物（补 logs//.log/.jsonl）。"""
    from agent import empty_run_gate as g
    for k in ("logs/", ".log", ".jsonl"):
        assert k in g.WORK_MEMORY_KEYS
    assert g.is_deliverable_path(_MIMIR + "/logs/agent.log") is False
    assert g.is_deliverable_path(_MIMIR + "/data/ops/x.jsonl") is False


def test_p0_1_real_card_write_still_counts(tmp_path):
    """正控：真写交付卡 ⇒ 仍判「写了」（不得为治误真而治死真）。

    注意：判据是**纯字符串分析**（不执行被测代码），故这里用交付面路径字面量；
    `tmp_path` 落在 `/tmp/` 下 = staging（`STAGING_MARKERS` 命中）⇒ 不能当正控。
    """
    from agent import empty_run_gate as g
    card = _WIKI + "/discussions/_p0_1_probe_literal.md"
    msgs = [{"role": "user", "content": "任务：落盘"},
            _p01_ec(11, "open(%r,'a').write('y')" % card)]
    assert g.is_deliverable_path(card) is True
    assert g.deliverable_written(msgs) is True
    assert g.staging_writes(msgs) == []


def test_p0_1_staging_draft_still_collected(tmp_path):
    """正控：staging 草稿仍被 A 段认到（flush 有料可救）。"""
    from agent import empty_run_gate as g
    draft = tmp_path / "tmp" / "b2" / "src.md"
    draft.parent.mkdir(parents=True, exist_ok=True)
    draft.write_text("d", encoding="utf-8")
    msgs = [{"role": "user", "content": "任务：落盘"},
            _p01_ec(12, "pathlib.Path(%r).open('a').write('x')" % str(draft))]
    assert g.staging_writes(msgs) == [str(draft)]


# ===== P1（2026-09-29 · 审计会4 附带）· 排除面单一真源 =====
# 病：agent_loop._check_has_written 曾自带一份三项硬编码排除清单（缺 logs/ · .log ·
#   .jsonl · run-log/）⇒ 与 empty_run_gate 口径分裂：只写 logs/*.log 的 run，闸门判
#   「非交付」而本函数判「已写」= 兄弟量具对同一事实给相反读数。
# 回归含义：把「日志写 ≠ 交付写」钉成用例；并断言两量具**同判**（单一真源）。
class _DummyAgent:
    _empty_run_flushed_paths = None


def _has_written(msgs):
    return MimirAgentLoop._check_has_written(_DummyAgent(), msgs)


def _wf(path):
    return [{"role": "assistant",
             "tool_calls": [_tc("write_file", {"path": path, "content": "x"})]}]


def test_p1_logs_write_is_not_a_deliverable_write():
    """日志写污染：唯一写目标是 logs/*.log ⇒ 不得判「写了交付物」。"""
    assert _has_written(_wf(_MIMIR + "/logs/agent.log")) is False


def test_p1_jsonl_and_runlog_are_not_deliverables():
    assert _has_written(_wf(_MIMIR + "/logs/run.jsonl")) is False
    assert _has_written(_wf(_MIMIR + "/run-log/x.md")) is False


def test_p1_staging_is_not_a_deliverable_write():
    assert _has_written(_wf(_MIMIR + "/tmp/draft.md")) is False


def test_p1_real_deliverable_still_counts():
    assert _has_written(_wf(_WIKI + "/discussions/x.md")) is True


def test_p1_exclusion_is_single_source():
    """口径一致性：empty_run_gate.is_deliverable_path 与 agent_loop._check_has_written 须同判。"""
    for c in [_MIMIR + "/logs/agent.log",
              "/tmp/x.md",
              _MIMIR + "/PROGRESS.md",
              _MIMIR + "/logs/x.jsonl",
              _WIKI + "/discussions/x.md"]:
        assert erg.is_deliverable_path(c) == _has_written(_wf(c)), c


# ===== P0-3（2026-10-07 · Hermes 复核 #12 补刀）· 临时目录**环境无关** =====
# 病：staging 判据写死字面量 "/tmp/" ⇒ TMPDIR 非 /tmp 的环境（Hermes 会话默认
#   ~/.hermes/cache/scratch）里，写进临时目录的草稿不算 staging ⇒ 反被读成「写了
#   交付物」⇒ 只读连续计数被清零 ⇒ 闸门被临时路径解除（P0-2 的病换路径复发）。
# 回归含义：临时目录由 tempfile.gettempdir() 拼（**不写死 /tmp**）⇒ 换环境不误红；
#   并断言该路径**确实**被判 staging / 非交付（否则用例只是「没写 /tmp」的空壳）。
import tempfile as _tempfile  # noqa: E402


def _td_staging_file(name="draft.md"):
    """临时目录里的草稿路径 —— 用运行期真源拼，禁写死 /tmp。"""
    return str(pathlib.Path(_tempfile.gettempdir()) / "erg_staging" / name)


def test_p0_3_tempdir_is_staging_regardless_of_tmpdir():
    p = _td_staging_file()
    assert erg.is_staging_path(p) is True, "临时目录（tempfile.gettempdir()）必须判 staging：" + p
    assert erg.is_deliverable_path(p) is False
    assert erg.is_staging_path("/tmp/x.md") is True, "字面量 /tmp/ 兼容面不得丢"
    assert _has_written(_wf(p)) is False, "临时目录写入不得算「有产出」（兄弟量具须同判）"


def test_p0_3_tempdir_draft_does_not_reset_readonly_budget(tmp_path):
    """行为级：写临时目录草稿 ⇒ 只读计数**不清零**（= Hermes 报的 5 failed 根因）。"""
    card = tmp_path / (CARD_PREFIX + "_P03.md")
    turns = ([("read", tmp_path / "a.md")] * 3 + [("write", _td_staging_file())]
             + [("read", tmp_path / "c.md")] * 2)
    assert erg.readonly_streak(_msgs(turns, card)) == 6, "tmp 草稿不得退还只读预算"
    gate = erg.EmptyRunGate(task_id="p03", limit=4, force_writes=1)
    assert gate.tick(_msgs(turns, card), 6) is not None, "staging 写不得解除拦截"
