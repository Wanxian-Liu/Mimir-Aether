"""run-boundary self-fix regression tests (2026-08-30).

三项修复的回归防护：
  A. agent_loop natural 退出前未完成计划检测（_last_assistant_unfinished + nudge 上限）
  B. execution_recorder close() 自动落盘 PROGRESS.md（task_name + 状态 + 未完成 [ ] 项）
  C. input 预处理：序号(1. 2. 3.) → [ ] 格式归一化（normalize_task_spec_checkboxes）
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent.task_completion import normalize_task_spec_checkboxes
from agent.execution_recorder import ExecutionRecorder


# ── 修复A：_last_assistant_unfinished（通过最小实例绕开 __init__ 依赖）──

def _make_loop():
    # 修复A 的逻辑在核心类 MimirAgentLoop（natural 退出路径所在）
    from agent.agent_loop import MimirAgentLoop
    loop = object.__new__(MimirAgentLoop)
    return loop


def _msgs_with_last(content, role="assistant"):
    return [{"role": "user", "content": "任务书"}, {"role": role, "content": content}]


def test_a_colon_ending_is_unfinished():
    """实证信号：最后输出"读剩余5个文件全文："（冒号结尾半句）→ 应判未完成"""
    loop = _make_loop()
    msgs = _msgs_with_last("读剩余5个文件全文：")
    assert loop._last_assistant_unfinished(msgs) is True


def test_a_plan_prefix_with_list_is_unfinished():
    """计划复述：接下来开头 + 列表 → 应判未完成"""
    loop = _make_loop()
    msgs = _msgs_with_last("接下来我将：\n- 读文件A\n- 读文件B")
    assert loop._last_assistant_unfinished(msgs) is True


def test_a_normal_finish_is_not_unfinished():
    """正常收尾（句号结尾、无计划前缀）→ 不应判未完成"""
    loop = _make_loop()
    msgs = _msgs_with_last("已完成全部修复，验证通过。")
    assert loop._last_assistant_unfinished(msgs) is False


def test_a_last_tool_message_ignored():
    """最后消息是 tool（非 assistant）→ 不判未完成（没有 assistant 产出）"""
    loop = _make_loop()
    msgs = [{"role": "user", "content": "任务书"}, {"role": "tool", "content": "ok"}]
    assert loop._last_assistant_unfinished(msgs) is False


def test_a_multimodal_content_joined():
    """多模态 content（list 形式）→ 拼接 text 段后判断"""
    loop = _make_loop()
    msgs = [{
        "role": "assistant",
        "content": [{"type": "text", "text": "继续读取剩余文件："}],
    }]
    assert loop._last_assistant_unfinished(msgs) is True


# ── 修复B：execution_recorder close() 落盘 PROGRESS.md ──

def test_b_close_appends_progress_md(tmp_path, monkeypatch):
    """close() 应把 task_name + 状态 + 未完成 [ ] 项追加写入 PROGRESS.md"""
    import agent.execution_recorder as er_mod

    captured = []

    def fake_append(self, exit_reason, task_spec):
        captured.append((self._task_name, exit_reason, task_spec))

    monkeypatch.setattr(er_mod.ExecutionRecorder, "_append_progress_md", fake_append)
    rec = ExecutionRecorder(task_name="fix-b-test", session_id="fixb-sess")
    rec.close(
        exit_reason="natural",
        final_response_summary="done",
        task_spec="- [ ] 修复A\n- [x] 修复B\n- [ ] 修复C",
    )
    assert len(captured) == 1
    name, reason, spec = captured[0]
    assert name == "fix-b-test"
    assert reason == "natural"
    assert "- [ ] 修复A" in spec
    assert "- [ ] 修复C" in spec


def test_b_progress_md_format(tmp_path, monkeypatch):
    """真实 _append_progress_md：incomplete 状态 + 未完成项按行追加"""
    import agent.execution_recorder as er_mod
    from agent.execution_recorder import ExecutionRecorder

    home = tmp_path / "mimiraether"
    home.mkdir()
    progress = home / "PROGRESS.md"
    progress.write_text("# PROGRESS\n", encoding="utf-8")

    monkeypatch.setattr(er_mod.os.path, "expanduser", lambda p: str(home) if p.startswith("~") else p)

    rec = ExecutionRecorder(task_name="fix-b-real", session_id="fixb-real")
    rec._append_progress_md(
        exit_reason="circuit_breaker",
        task_spec="- [ ] 读文件A\n- [ ] 写报告",
    )
    out = progress.read_text(encoding="utf-8")
    assert "# PROGRESS" in out  # 原内容保留（追加式）
    assert "run: fix-b-real" in out
    assert "status: **incomplete**" in out
    assert "exit_reason: `circuit_breaker`" in out
    assert "- [ ] 读文件A" in out
    assert "- [ ] 写报告" in out


# ── 修复C：normalize_task_spec_checkboxes ──

def test_c_english_numbered_steps_converted():
    inp = "1. 修复A\n2. 修复B\n3. 修复C"
    out = normalize_task_spec_checkboxes(inp)
    assert out == "- [ ] 修复A\n- [ ] 修复B\n- [ ] 修复C"


def test_c_cn_dunhao_steps_converted():
    out = normalize_task_spec_checkboxes("1、修复A\n2、修复B")
    assert out == "- [ ] 修复A\n- [ ] 修复B"


def test_c_paren_steps_converted():
    out = normalize_task_spec_checkboxes("1) 修复A\n2) 修复B")
    assert out == "- [ ] 修复A\n- [ ] 修复B"


def test_c_existing_checkbox_untouched():
    inp = "- [ ] 修复A\n- [x] 修复B"
    assert normalize_task_spec_checkboxes(inp) == inp


def test_c_single_step_not_converted():
    """单序号不转换（防误伤正文）"""
    inp = "只有一个步骤 1. 修复A"
    assert normalize_task_spec_checkboxes(inp) == inp


def test_c_plain_text_untouched():
    inp = "普通消息没有任何序号"
    assert normalize_task_spec_checkboxes(inp) == inp
