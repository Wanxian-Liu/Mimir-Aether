"""exit_reason 恒假修复回归（2026-09-27 · Mimir 定因）

被测缺陷：tools/delegate_tool.py 旧写法读 result 的 completed 键并以 False 兜底；
生产端 run_conversation 返回值**不写**该键 ⇒ 恒判「未完成」⇒ 三分支永远落到 else
⇒ 委派台账 exit_reason **恒为** max_iterations（实测：子代理只跑 4/12 轮、10.7 秒
正常收尾也被贴成「撞限」，导致成败字段不可用）。

修复：_derive_child_completed（键缺失时用 exit_reason=natural 推断）
      + _derive_child_exit_reason（透传真实失败原因，缺省才兜底）。

臂型：B = 行为级（调真实函数）· S = 结构闸（只读源码）· 差分 = 证明本组有鉴别力
"""
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from tools import delegate_tool as D


def test_b_natural_without_completed_key_is_completed():
    """正控：无 completed 键 + exit_reason=natural ⇒ 判完成（旧写法判 False）。"""
    r = {"exit_reason": "natural", "final_response": "answer"}
    assert D._derive_child_completed(r) is True
    assert D._derive_child_exit_reason(r, True, False) == "completed"


def test_b_max_turns_not_completed_and_reason_passthrough():
    """负控①：exit_reason=max_turns ⇒ 非完成，且透传真实原因。"""
    r = {"exit_reason": "max_turns"}
    assert D._derive_child_completed(r) is False
    reason = D._derive_child_exit_reason(r, False, False)
    assert reason == "max_turns"
    assert reason != "completed"
    assert reason != "max_iterations"


def test_b_missing_reason_falls_back_to_max_iterations():
    """负控②：连 exit_reason 也缺 ⇒ 才退回 max_iterations（兜底不得被删）。"""
    r = {}
    assert D._derive_child_completed(r) is False
    assert D._derive_child_exit_reason(r, False, False) == "max_iterations"


def test_b_explicit_key_wins():
    """兼容臂：显式 completed 键存在时以其为准（False 不被 natural 覆盖）。"""
    assert D._derive_child_completed({"completed": True}) is True
    assert D._derive_child_completed({"completed": False, "exit_reason": "natural"}) is False


def test_b_interrupted_takes_precedence():
    """序臂：interrupted 优先于 completed。"""
    r = {"exit_reason": "natural"}
    assert D._derive_child_exit_reason(r, True, True) == "interrupted"


def test_differential_naive_form_would_misclassify():
    """差分：旧写法对同一输入给 False ⇒ 证明上面各臂有鉴别力。"""
    r = {"exit_reason": "natural"}
    assert r.get("completed", False) is False
    assert D._derive_child_completed(r) is True


def test_s_no_naive_completed_read_in_source():
    """S：源码不得再出现裸读 completed 键并以 False 兜底（防复发）。"""
    src = (REPO / "tools/delegate_tool.py").read_text(encoding="utf-8")
    assert 'get("completed", False)' not in src


def test_s_callers_use_pure_helpers():
    """S：生产路径确实调用两个纯函数（防「函数在、没接线」）。"""
    src = (REPO / "tools/delegate_tool.py").read_text(encoding="utf-8")
    assert "completed = _derive_child_completed(result)" in src
    assert "exit_reason = _derive_child_exit_reason(result, completed, interrupted)" in src
