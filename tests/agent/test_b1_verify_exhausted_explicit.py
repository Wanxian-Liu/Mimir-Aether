"""B1（2026-09-24 四方共识）twin-arm：废弃「research 实质回答豁免」出口的负控三臂。

背景：run 连续 4 次停在英文计划句（"Now Phase 1…"/"Let me read…"）被旧豁免「视为产出」放走。
臂 A 钉死病灶（旧函数对英文计划句放行）· 臂 B 钉死修复（豁免出口零调用）· 臂 C 钉死新行为（3/3 明示分支在）。
"""
import ast
from pathlib import Path
from types import SimpleNamespace

AGENT_LOOP = Path(__file__).resolve().parents[2] / "agent" / "agent_loop.py"
_SRC = AGENT_LOOP.read_text(encoding="utf-8")


def _fake_loop():
    from agent.agent_loop import MimirAgentLoop
    return SimpleNamespace(_SYS_MARKS=MimirAgentLoop._SYS_MARKS, _STOP_WORDS=MimirAgentLoop._STOP_WORDS)


def _call_old_exemption(messages):
    from agent.agent_loop import MimirAgentLoop
    return MimirAgentLoop._is_substantive_research_answer(_fake_loop(), messages)


def test_arm_a_english_plan_sentence_was_exempted():
    """臂 A（旧形态活证据）：≥50 字英文计划句曾被判「实质回答」⇒ 视为产出放走。"""
    plan_msgs = [{"role": "assistant",
                  "content": "Found the pinned card. Let me read the B1 spec (section 16) and the "
                             "exemption function body now before touching any production code."}]
    assert _call_old_exemption(plan_msgs) is True, "旧豁免对英文计划句必须放行（钉死病灶——这就是拦腰 4 次的机理）"


def test_arm_a2_chinese_signal_table_gap_is_documented():
    """臂 A2：未完成信号词表为纯中文——英文将来时信号不在表内（病灶机理钉死）。"""
    from agent.agent_loop import MimirAgentLoop
    import inspect, re
    src = inspect.getsource(MimirAgentLoop._is_substantive_research_answer)
    table = re.search(r'if any\(w in _text for w in \(([^)]*)\)\)', src)
    assert table, "信号词表必须可定位"
    assert not re.search(r'[a-zA-Z]{3,}', table.group(1)), "词表应为纯中文（病灶事实）——若已双语化请同步更新本臂"


def test_arm_b_no_production_caller_of_exemption():
    """臂 B（新形态）：豁免出口在生产路径零调用（B1 已拆）。"""
    tree = ast.parse(_SRC)
    calls = [n for n in ast.walk(tree)
             if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
             and n.func.attr == "_is_substantive_research_answer"]
    assert calls == [], f"豁免出口必须零调用，实测 {len(calls)} 处"


def test_arm_c_explicit_fault_raised_not_just_rendered():
    """臂 C（T4 2026-09-26 强化 · 治 BR-4 假绿臂）：明示故障必须由**专用 reason 退出**承载。

    本臂 v1 只查「源码含某串」⇒ 漏掉 BR-1（死变量：文案赋给局部变量后零读取）与
    BR-2（出口不带故障态：代码继续落穿 ⇒ reason="natural" ⇒ 未验证回复被原样投出）——
    「源码里有这行字」与「真会明示」是两件事。T4 改为结构性双端断言：

      ① 生产端：以 `verify_exhausted` 退出（不再是自然出口）；
      ② 消费端：core_loop 有该 reason 的专用分支（文案有真实落点）；
      ③ **行为级**验收（真 loop 跑出该 reason）在
         `tests/agent/test_t4_verify_exhausted_wired.py::test_armE_producer_exits_with_verify_exhausted`
         —— 本臂不再承担行为验证，只钉「两端接线存在」。
    """
    assert "B1 明示故障（verify 3/3 耗尽 + has_written=False）" in _SRC
    assert 'raise AgentLoopExit("verify_exhausted"' in _SRC, (
        "生产端必须以专用 reason 退出（否则落穿 natural ⇒ 交付层投出未验证回复）"
    )
    _core = (Path(__file__).resolve().parents[2] / "agent" / "core_loop.py").read_text(encoding="utf-8")
    assert 'elif _exit_reason == "verify_exhausted":' in _core, (
        "消费端必须有该 reason 的专用明示分支（文案须有落点，不得只存在于生产者局部变量里）"
    )
    # 旧豁免日志行必须消失
    assert "research 实质回答豁免（≥50字+实词≥10）——视为产出，自然退出" not in _SRC


def test_arm_d_function_kept_for_history():
    """臂 D：旧函数保留为活证据（docstring 标注 B1 废弃·零调用）。"""
    from agent.agent_loop import MimirAgentLoop
    import inspect
    doc = inspect.getsource(MimirAgentLoop._is_substantive_research_answer)
    assert "B1 废弃 2026-09-24" in doc
