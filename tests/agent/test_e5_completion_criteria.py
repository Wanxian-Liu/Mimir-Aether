"""E5 实验卡：完成判据从「写盘」改为「可验证产出」。

A1 = 否定语境短路（verify_before_report_guard._task_requires_write）
A2 = 证据型完成（agent_loop._check_has_evidence）

负控（必须转红，否则等于没修）：
  · A2 对「工具调用存在但结果空 / 报错 / 非信息型工具」必须 False
  · A1 用 env 回滚到病形态时，「不要落盘」必须重新被判为写盘任务（受控差分）
  · 既有空洞确认拦截不得被 A1 松动
"""
import os

import agent.verify_before_report_guard as vg
import agent.agent_loop as al

# 原文照抄（只把家目录写成可推导形式——仓内禁真实家目录字面量，pre-push 闸强制）。
# 本用例的载荷是「（不要落盘、不要修改任何文件）」这个**否定短语**，与路径无关。
_REAL_TASK = ("读取 /home/<user>/src/MimirAether/README.md 的前 5 行，以及 "
              "/home/<user>/src/MimirAether/VERSION 的内容，把两者的原文直接返回给我"
              "（不要落盘、不要修改任何文件）。")


def _user(t):
    return [{"role": "user", "content": t}]


def _tc(name, tid="c1"):
    return {"id": tid, "type": "function", "function": {"name": name, "arguments": "{}"}}


def _read_run(content_len=400, tool="read_file"):
    return [
        {"role": "user", "content": "读取文件并把原文返回"},
        {"role": "assistant", "content": "", "tool_calls": [_tc(tool)]},
        {"role": "tool", "tool_call_id": "c1", "content": "x" * content_len},
        {"role": "assistant", "content": "**原文如下**：..."},
    ]


_LOOP_CLS = next(c for c in vars(al).values()
                 if isinstance(c, type) and hasattr(c, "_check_has_evidence"))


def _evidence(messages):
    return _LOOP_CLS._check_has_evidence(_LOOP_CLS.__new__(_LOOP_CLS), messages)


# ---------------- A1 否定语义 ----------------
def test_a1_real_e2e_task_no_longer_a_write_task():
    """决定性回归：原文含「不要落盘」⇒ 不得判为写盘任务。"""
    assert vg._task_requires_write(_user(_REAL_TASK)) is False


def test_a1_positive_write_task_still_detected():
    assert vg._task_requires_write(_user("把这批结论落盘到 notes")) is True


def test_a1_positive_other_marker():
    assert vg._task_requires_write(_user("帮我创建一份报告")) is True


def test_a1_mixed_negated_then_positive_still_write_task():
    assert vg._task_requires_write(_user("不要写代码，但把结论落盘")) is True


def test_a1_positive_unrelated_context_not_negated():
    assert vg._task_requires_write(_user("先读一遍，然后写到 notes/ 里")) is True


def test_a1_rollback_env_restores_legacy_differential(monkeypatch):
    """受控差分：关掉 A1 ⇒ 病形态复现（「不要落盘」被判写盘任务）。"""
    monkeypatch.setenv("MIMIR_WRITE_TASK_NEGATION", "0")
    assert vg._task_requires_write(_user("不要落盘")) is True


# ---------------- A2 证据型完成 ----------------
def test_a2_evidence_present():
    assert _evidence(_read_run()) is True


def test_a2_negative_no_tool_calls():
    assert _evidence([{"role": "user", "content": "报告"},
                      {"role": "assistant", "content": "我看了"}]) is False


def test_a2_negative_empty_result():
    assert _evidence(_read_run(content_len=5)) is False


def test_a2_negative_error_result():
    r = _read_run()
    r[2]["content"] = "[ERROR] path not found: /nope"
    assert _evidence(r) is False


def test_a2_negative_write_only_tool_is_not_evidence():
    r = _read_run()
    r[1]["tool_calls"] = [_tc("write_file")]
    assert _evidence(r) is False


def test_a2_rollback_env(monkeypatch):
    monkeypatch.setenv("MIMIR_EVIDENCE_COMPLETION", "0")
    assert _evidence(_read_run()) is False


# ---------------- 端到端：只读任务不再被拦 ----------------
def test_e2e_readonly_task_not_blocked_by_guard():
    msgs = [
        {"role": "user", "content": _REAL_TASK},
        {"role": "assistant", "content": "", "tool_calls": [_tc("read_file", "c1")]},
        {"role": "tool", "tool_call_id": "c1", "content": "# MimirAether\n" * 40},
        {"role": "assistant", "content": "**README 前 5 行原文**：```# MimirAether```"},
    ]
    assert vg.should_block_finish(msgs, msgs[-1]["content"]) is False


# ---------------- 接线守卫（防「助手存在但没人调」复发）----------------
def test_wired_into_completion_gate():
    src = open(al.__file__, encoding="utf-8").read()
    assert "_has_evidence = self._check_has_evidence(messages)" in src
    assert "not _has_evidence" in src


# ---------------- 既有空洞确认拦截不得被 A1 松动 ----------------
def test_hollow_ack_still_blocked():
    msgs = [{"role": "user", "content": "把这批结论落盘"}]
    assert vg.should_block_finish(msgs, "收到——落盘") is True


def test_hollow_ack_still_blocked_with_negation_env(monkeypatch):
    monkeypatch.setenv("MIMIR_WRITE_TASK_NEGATION", "0")
    msgs = [{"role": "user", "content": "把这批结论落盘"}]
    assert vg.should_block_finish(msgs, "收到——落盘") is True
