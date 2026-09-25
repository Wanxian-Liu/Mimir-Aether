"""T4（2026-09-26 · 卡 §BR-1/BR-2/BR-4 收口）——「明示故障」不再只是死变量。

病灶（本单起点，盘上原文）
  `agent/agent_loop.py` 的 B1 分支把故障文案赋给局部变量 `content`，赋值后**全程零读取**
  （死变量 = BR-1）；且**不 raise**，继续落穿到自然出口 ⇒ `reason="natural"`
  ⇒ core_loop 按「natural 取当前回复」把**未通过验证的回复原样投出**（BR-2：出口未带故障态）。
  ⇒ 该分支「明示故障」的意图在**交付层收益 = 0**。

  旧测法（`tests/agent/test_b1_verify_exhausted_explicit.py` 臂 C）只断言「源码含某串」
  ⇒ 漏掉 BR-1/BR-2（BR-4：假绿臂）。本文件补**行为臂**，并锁死「死变量」这一类不变式。

各臂（每条对「旧形态必红」给出可复现负控）
  A   负控（病可复现·真生产块）: reason="natural" + 真 loop 产出的 messages ⇒ 未验证声明原样投出
  A2  受控差分（同一块删该分支）: ⇒ 落 fail-closed else ⇒ 文案变「没调到模型」（谎：模型调到了）
  B   新形态（盘上真源）        : reason="verify_exhausted" ⇒ 故障文案（≠ 声明）
  C   孪生（回归）              : billing_exhausted / max_turns 文案逐字保留
  D   守卫                      : interrupted=True ⇒ 不被明示覆盖；生产者亦不得标 interrupted
  E   生产者（真 loop 行为）    : guard 开 ⇒ exit_reason == "verify_exhausted"
  E2  孪生（guard 关）          : ⇒ exit_reason == "natural"（证明臂 E 测的是闸本身）
  F   结构性不变式（死变量类）  : `_loop_body` 内 content 赋值必须有后续读取
  F2  负控                      : 同一检测器对病形态冻结件必须报警（否则臂 F 是假绿）
  G   量具接线 + 污染防护       : 真 loop 一次 ⇒ verification ledger 落账 ≥1 且在隔离 home 内
  H   cron 台账归类             : cron_run_outcome({"exit_reason":"verify_exhausted"}) == error
"""
from __future__ import annotations

import ast
import asyncio
import pathlib
import textwrap

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
AGENT_LOOP = REPO_ROOT / "agent" / "agent_loop.py"
CORE_LOOP = REPO_ROOT / "agent" / "core_loop.py"

_START = '_final_content = ""'
_END = "if _result.interrupted:"

UNVERIFIED_CLAIM = "已完成落盘与验证：本轮全部项目通过，零失败"
EARLIER_ASSISTANT = "上一轮的旧回复（不该被当成最终答复）"
PRODUCER_MESSAGES = [
    {"role": "user", "content": "请修复 X 并把结论落盘到 notes/ 下"},
    {"role": "assistant", "content": EARLIER_ASSISTANT},
    {"role": "user", "content": "[BLOCKED:verify-before-report] 你的回复被阻止……"},
    {"role": "assistant", "content": UNVERIFIED_CLAIM},
]


class _Logger:
    def __init__(self) -> None:
        self.errors: list = []

    def error(self, *a, **k):
        self.errors.append(a)


class _Result:
    def __init__(self, exit_reason: str, interrupted: bool, messages: list, turns_used: int = 4):
        self.exit_reason = exit_reason
        self.interrupted = interrupted
        self.messages = messages
        self.turns_used = turns_used


# ===========================================================================
# 生产块抽取（**不复制**判据代码——从盘上真源抽，防「测的是转述」）
# ===========================================================================

def _extract_block() -> str:
    lines = CORE_LOOP.read_text(encoding="utf-8").splitlines(keepends=True)
    start = next((i for i, ln in enumerate(lines) if ln.strip() == _START), None)
    assert start is not None, f"锚点丢失：{_START!r} 不在 {CORE_LOOP}"
    end = next((i for i, ln in enumerate(lines[start:], start)
                if ln.strip().startswith(_END)), None)
    assert end is not None, f"锚点丢失：{_END!r} 不在 {CORE_LOOP}"
    block = "".join(lines[start:end])
    assert '"natural"' in block and "fail-closed" in block, "抽到的块不含 fail-closed 判定——锚点漂了"
    assert "verify_exhausted" in block, "抽到的块不含 T4 新增分支——锚点漂了"
    return textwrap.dedent(block)


def _strip_verify_branch(block: str) -> str:
    """受控差分：同一块删掉 elif _exit_reason == "verify_exhausted" 整段（到 else 前）。"""
    lines = block.splitlines(keepends=True)
    key = 'elif _exit_reason == "verify_exhausted":'
    start = next(i for i, ln in enumerate(lines) if key in ln)
    end = next(i for i, ln in enumerate(lines[start:], start) if ln.strip() == "else:")
    return "".join(lines[:start] + lines[end:])


def _run(block: str, exit_reason: str, interrupted: bool, messages: list):
    lg = _Logger()
    ns = {
        "_result": _Result(exit_reason, interrupted, messages),
        "logger": lg,
        "task_id": "t4test0000",
        "getattr": getattr,
    }
    exec(compile(textwrap.dedent(block), "<core_loop.py:final-content-branch>", "exec"), ns)
    return ns["_final_content"], lg


# ===========================================================================
# 臂 A / A2 / B：交付层（消费者）
# ===========================================================================

def test_armA_negative_control_natural_replays_unverified_claim():
    """臂 A（病可复现）：旧生产者在同一批 messages 上给 reason="natural" ⇒ 未验证声明原样投出。"""
    content, lg = _run(_extract_block(), "natural", False, PRODUCER_MESSAGES)
    assert content == UNVERIFIED_CLAIM, "旧形态应原样投出未验证声明——这就是 BR-1/BR-2 的交付层形态"
    assert not lg.errors


def test_armA2_differential_branch_removed_falls_to_misleading_text():
    """臂 A2（受控差分）：同一块删掉 verify_exhausted 分支 ⇒ 落 else ⇒「没调到模型」（谎）。"""
    stripped = _strip_verify_branch(_extract_block())
    assert "verify_exhausted" not in stripped, "差分件必须真的删掉了该分支"
    content, lg = _run(stripped, "verify_exhausted", False, PRODUCER_MESSAGES)
    assert content != UNVERIFIED_CLAIM, "即使走兜底也不得复读未验证声明（fail-closed 兜底）"
    assert "没调到模型" in content, "负控钉死：缺该分支时文案退化为「没调到模型」——模型其实调到了（假故障）"
    assert lg.errors


def test_armB_new_form_emits_fault_notice_not_claim():
    """臂 B（新形态·盘上真源）：verify_exhausted ⇒ 投出故障文案，且不是那条未验证声明。"""
    content, lg = _run(_extract_block(), "verify_exhausted", False, PRODUCER_MESSAGES)
    assert content != UNVERIFIED_CLAIM, "行为契约：投出文案 ≠ 最后一条 assistant content"
    assert content != EARLIER_ASSISTANT, "也不得复读更早的旧回复"
    assert content.startswith("[故障明示]"), "须留在既有三互斥前缀内（不新造第 4 前缀）"
    assert "verify-before-report" in content and "3/3" in content, "文案须点明是验证闸耗尽，不是 provider 故障"
    assert "reason=verify_exhausted" in content, "原样 reason 须可 grep（Q6 投递对账按串归因）"
    assert "没调到模型" not in content, "文案失真守卫：不得谎称 API/连续错误（模型调到了）"
    assert "不重发旧回复" in content
    assert lg.errors, "明示必须留日志（零新增埋点：复用现有 logger.error）"


# ===========================================================================
# 臂 C / D：孪生与守卫（防「一刀切明示」打红既有路径）
# ===========================================================================

def test_armC_twin_special_texts_preserved():
    """臂 C（回归）：billing 断粮 / max_turns 到顶文案逐字保留（诊断价值不回退）。"""
    block = _extract_block()
    billing, _ = _run(block, "billing_exhausted", False, PRODUCER_MESSAGES)
    assert billing.startswith("[断粮]") and "402/billing" in billing
    mx, _ = _run(block, "max_turns", False, PRODUCER_MESSAGES)
    assert mx.startswith("[故障明示]") and "reason=max_turns" in mx


def test_armD_interrupted_not_overridden_by_notice():
    """臂 D（守卫）：interrupted=True ⇒ 走既有早退，不被明示覆盖；生产者亦不得标 interrupted。"""
    content, lg = _run(_extract_block(), "verify_exhausted", True, PRODUCER_MESSAGES)
    assert not content.startswith("[故障明示]"), "interrupted 分支优先——中断臂不得被明示覆盖"
    assert not lg.errors
    src = AGENT_LOOP.read_text(encoding="utf-8")
    # 逐 raise 检查（顺序改造后该区域还含 L3 的 interrupt 载荷 —— 那个 "interrupted": True 是
    # 合法且必须保留的；要钉的是 **verify_exhausted 的载荷**里不得出现它）
    key = 'AgentLoopExit("verify_exhausted"'
    assert key in src, "生产者必须以专用 reason 退出"
    idx, seen = 0, 0
    while True:
        idx = src.find(key, idx)
        if idx == -1:
            break
        seen += 1
        payload = src[idx:idx + 300]
        assert '"interrupted"' not in payload, (
            f"verify_exhausted 的载荷不得带 interrupted（第 {seen} 处）"
            "—— 那会落进 core_loop 的取当前回复分支（回退成复读）"
        )
        idx += len(key)
    assert seen >= 1


# ===========================================================================
# 臂 E / E2 / G：生产者（真 loop 行为）
# ===========================================================================

_CLAIM_REPLY = "已完成落盘与验证：本轮全部项目通过"


def _resp(text: str):
    msg = type("M", (), {"content": text, "tool_calls": None})()
    choice = type("C", (), {"message": msg})()
    return type("R", (), {"choices": [choice]})()


def _run_real_loop(monkeypatch, tmp_path, guard_on: bool, max_turns: int = 8,
                   enforce: bool = False):
    from agent.agent_loop import MimirAgentLoop

    monkeypatch.setenv("MIMIR_VERIFY_BEFORE_REPORT", "1" if guard_on else "0")
    monkeypatch.setenv("MIMIR_PRODUCTION_ENFORCE", "1" if enforce else "0")
    ledger = tmp_path / "verification_results.jsonl"
    monkeypatch.setenv("MIMIR_VERIFICATION_RESULTS_PATH", str(ledger))

    async def chat(messages):
        return _resp(_CLAIM_REPLY)

    loop = MimirAgentLoop(
        model_call=chat,
        tool_schemas=[],
        valid_tool_names=set(),
        tool_dispatcher=lambda name, args, tc_id: "noop",
        max_turns=max_turns,
        task_id="t4loop0001",
    )
    return asyncio.run(
        loop.run([{"role": "user", "content": "请修复 X 并把结论落盘到 notes/ 下"}])
    )


def test_armE_producer_exits_with_verify_exhausted(monkeypatch, tmp_path):
    """臂 E（核心行为臂）：真 loop + 闸连拦 3 次 + 零落盘 ⇒ exit_reason=verify_exhausted。

    旧形态此处必得 natural（B1 分支只赋值不退出）——本臂即 BR-1/BR-2 的机检。
    """
    res = _run_real_loop(monkeypatch, tmp_path, guard_on=True)
    assert res.exit_reason == "verify_exhausted", (
        f"生产者必须以专用 reason 退出（实测 {res.exit_reason!r}）——"
        "若得 natural，说明又落穿到自然出口，交付层会把未验证声明原样投出"
    )
    assert res.finished_naturally is False
    assert res.interrupted is False, "不得标 interrupted（否则 core_loop 走取当前回复分支）"
    lasts = [m.get("content") for m in res.messages if m.get("role") == "assistant"]
    assert lasts and lasts[-1] == _CLAIM_REPLY, "前提校验：messages 末条确实是那条未验证声明"


def test_armE2_twin_guard_off_still_natural(monkeypatch, tmp_path):
    """臂 E2（孪生）：关闸（MIMIR_VERIFY_BEFORE_REPORT=0）⇒ 仍 natural（证明臂 E 测的是闸本身）。"""
    res = _run_real_loop(monkeypatch, tmp_path, guard_on=False)
    assert res.exit_reason == "natural", f"关闸后不应出现 verify_exhausted（实测 {res.exit_reason!r}）"


def test_armG_ledger_wired_and_isolated(monkeypatch, tmp_path):
    """臂 G：真 loop 判定 3 次 ⇒ 量具落账 ≥1，且路径在隔离 home 内（不污染生产台账）。"""
    from agent.verification_ledger import ledger_path

    _run_real_loop(monkeypatch, tmp_path, guard_on=True)
    path = ledger_path()
    assert str(tmp_path) in str(path), f"量具路径必须被隔离（实测 {path}）"
    assert path.exists(), "verify 判定必须落账（R2 量具接线回归）"
    n = sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip())
    assert n >= 1, f"三次真实判定应留下 ≥1 条记录（实测 {n}）"


# ===========================================================================
# 臂 F / F2：结构性不变式（死变量类）——修一个实例，钉一整类
# ===========================================================================

_FROZEN_DEAD_ASSIGN = '''
async def _loop_body(self, messages):
    if verify_nudges >= MAX_VERIFY_NUDGES:
        content = "[故障明示] verify-before-report 闸 3/3 耗尽"
    raise AgentLoopExit("natural", {"messages": messages})
'''


def _dead_content_assigns(src: str) -> list:
    """`_loop_body` 内对 name='content' 的赋值中，**没有后续读取**的行号（死变量）。"""
    tree = ast.parse(src)
    fn = next((n for n in ast.walk(tree)
               if isinstance(n, ast.AsyncFunctionDef) and n.name == "_loop_body"), None)
    assert fn is not None, "`_loop_body` 未找到——锚点漂了"
    assigns, loads = [], []
    for n in ast.walk(fn):
        if isinstance(n, ast.Name) and n.id == "content":
            (assigns if isinstance(n.ctx, ast.Store) else loads).append(n.lineno)
    return [ln for ln in assigns if not any(l > ln for l in loads)]


def test_armF_dead_content_invariant_on_live_source():
    """臂 F（真源）：盘上 `_loop_body` 内不存在「赋值后零读取」的 content。"""
    hits = _dead_content_assigns(AGENT_LOOP.read_text(encoding="utf-8"))
    assert hits == [], f"检测到死变量赋值（content 赋值后零读取）：行号 {hits}"


def test_armF2_detector_has_discriminating_power():
    """臂 F2（负控）：同一检测器对病形态冻结件必须报警——否则臂 F 恒绿、无鉴别力。"""
    hits = _dead_content_assigns(_FROZEN_DEAD_ASSIGN)
    assert len(hits) == 1, f"检测器对病形态必须报警 1 处（实测 {hits}）——否则臂 F 是假绿"


# ===========================================================================
# 臂 H：cron 台账归类
# ===========================================================================

def test_armH_cron_ledger_treats_verify_exhausted_as_error():
    """臂 H：verify 闸耗尽 = 该轮零落盘 ⇒ cron 台账必须记 error（否则重演 P0-A 假绿）。"""
    import sys

    sys.path.insert(0, str(REPO_ROOT))
    from gateway.cron_mixin import cron_run_outcome

    status, err = cron_run_outcome({"exit_reason": "verify_exhausted", "failed": False})
    assert status == "error", f"verify_exhausted 必须记 error（实测 {status!r}）"
    assert "verify_exhausted" in str(err), "错误信息须带原样 reason（供 cron 台账归因）"
    # 孪生：natural 仍记 ok
    ok_status, _ = cron_run_outcome({"exit_reason": "natural", "failed": False})
    assert ok_status == "ok", "natural 不得被误判为 error"


# ===========================================================================
# 臂 I / I2：顺序（BR-3）——L2/L3 的「先逼补产出」优先，终局才明示
# ===========================================================================

def test_armI_order_hard_chain_first_then_explicit_notice(monkeypatch, tmp_path):
    """臂 I（顺序臂·BR-3）：enforce=1 ⇒ 先走完 L1/L2/L3 硬拦截链（多轮尝试），终局**明示**。

    钉两件事：
      ① 顺序保留 —— 尝试轮数 > enforce=0 的臂 E（证明 L1/L2 真的跑了，没被明示抢占）；
      ② 终局不透传 —— `interrupted is False`（不透传那条未验证回复，与四方共识
         「Q3：透传=作弊，明示=诚实」一致）。
    """
    res = _run_real_loop(monkeypatch, tmp_path, guard_on=True, enforce=True, max_turns=12)
    assert res.exit_reason == "verify_exhausted", (
        f"拦不动时须明示而非透传（实测 {res.exit_reason!r}）——interrupt 会让交付层投出未验证回复"
    )
    assert res.interrupted is False, "不得走 interrupted 透传路径"
    assert res.turns_used >= 5, (
        f"须先走完硬拦截链再明示（实测 turns_used={res.turns_used}）——"
        "若 ≤4 说明明示抢占了 L1/L2/L3（BR-3 顺序被翻转）"
    )
    hard = [m for m in res.messages
            if m.get("role") == "user" and isinstance(m.get("content"), str)
            and "产出" in m.get("content", "")]
    assert hard, "硬拦截链的 nudge 必须真的注入过（顺序证据）"


def test_armI2_twin_non_verify_run_keeps_l3_passthrough(monkeypatch, tmp_path):
    """臂 I2（孪生）：非 verify-耗尽的 enforce 路径**保持原样** —— L3 中断(interrupted=True)透传。

    证明本单改动只作用于「verify 3/3 耗尽」子集，没有一刀切改掉 L3 语义。
    """
    res = _run_real_loop(monkeypatch, tmp_path, guard_on=False, enforce=True, max_turns=12)
    assert res.exit_reason == "interrupt", (
        f"非 verify 场景应仍走 L3 中断（实测 {res.exit_reason!r}）——本单不得改其语义"
    )
    assert res.interrupted is True


def test_armI3_consumer_interrupt_path_still_passthrough():
    """臂 I3（记录既有语义）：reason=interrupt + interrupted=True ⇒ 交付层仍取当前回复。

    这条**不是**要修的行为，而是把「透传」明确钉成可断言事实（透明化残留面）：
    仅当 verify 未耗尽时该路径才可达（臂 I2 已证）。
    """
    content, lg = _run(_extract_block(), "interrupt", True, PRODUCER_MESSAGES)
    assert content == UNVERIFIED_CLAIM, "既有 interrupt 透传语义（仅非 verify-耗尽场景可达）"
    assert not lg.errors
