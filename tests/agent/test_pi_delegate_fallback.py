"""PI 委派「全失败 → 降级标志」回归（2026-10-26 · 活体测试暴露的缺口）

实证（pi_delegate_live_test.py 阶段 A）：
    `subagent_bridge.PI_BIN` 指到不存在路径 ⇒ `spawn_multi` 返回 3 条
    `success=False`（"pi binary not found"），但 `maybe_pi_delegate_execute`
    仍返回 `delegated=True` 且**没有** fallback 标志 ⇒ 调用方会把「全灭」
    误读成「委派成功」。

本用例两向：全失败 ⇒ fallback=True ∧ error 非空；全成功 ⇒ 无 fallback。
"""
import os
import sys

REPO = os.environ.get("MIMIR_REPO_ROOT", os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, REPO)

import subagent_bridge  # noqa: E402
from agent.pi_trigger import maybe_pi_delegate_execute  # noqa: E402

DISPATCH = """【任务】PI 委派降级标志回归（批量独立子任务）

【背景】三条子任务相互独立，请分别验证，并汇总成清单。审计要求：全部真实执行。
请勿绕过、请勿跳过，最终输出清单。

【步骤】
- [ ] 输出 PI_SUBTASK_ONE_OK
- [ ] 输出 PI_SUBTASK_TWO_OK
- [ ] 输出 PI_SUBTASK_THREE_OK

【边界】不读文件、不跑命令、不扫描目录。
"""


class _R:
    """模仿 SubagentResult 的最小替身。"""

    def __init__(self, success, stdout="", error=None):
        self.success = success
        self.stdout = stdout
        self.error = error


def _run(monkey_result):
    old_guard = os.environ.get("MIMIR_DELEGATION_GUARD")
    old_spawn = subagent_bridge.spawn_multi
    os.environ["MIMIR_DELEGATION_GUARD"] = "0"   # 受控隔离闸③（短上下文必拦，与本题无关）
    subagent_bridge.spawn_multi = lambda tasks, parallel=True: [
        monkey_result for _ in tasks
    ]
    try:
        return maybe_pi_delegate_execute([{"role": "user", "content": DISPATCH}])
    finally:
        subagent_bridge.spawn_multi = old_spawn
        if old_guard is None:
            os.environ.pop("MIMIR_DELEGATION_GUARD", None)
        else:
            os.environ["MIMIR_DELEGATION_GUARD"] = old_guard


def test_all_subtasks_failed_sets_fallback():
    res = _run(_R(False, error="pi binary not found"))
    assert res["triggered"] is True
    assert res["delegated"] is True
    assert res.get("fallback") is True, "全失败必须显式置 fallback=True"
    assert res.get("error"), "全失败必须带可读 error（不静默）"
    assert all(r["success"] is False for r in res["results"])


def test_all_subtasks_ok_has_no_fallback():
    res = _run(_R(True, stdout="OK"))
    assert res["triggered"] is True
    assert res["delegated"] is True
    assert not res.get("fallback"), "全成功不得带 fallback"
    assert len(res["results"]) == 3
