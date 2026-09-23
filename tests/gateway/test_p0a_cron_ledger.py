"""P0-A (2026-09-23) — cron 台账「跑失败却记 ok」的假绿修复。

事故（盘上取证）：agent 型 cron job（P0 chroma 6h / wiki-quality-gate 12h）
自 2026-09-22 20:00 起 **5/5 连续**跑失败：

    09-22 02:41 / 08:00 / 08:42 / 14:42  → 1101~1323 B 真报告（15~142s）
    09-22 20:00 起连续 5 次               → **49 B**（5.9~6.2s）

那 49 B 经 sha1 定名 = core_loop 的异常退出兜底「故障明示」文案
（`sha1_12=072e8c27d368`，逐字符 **49**，见 `tmp/p0a_id49_probe.py`）。
而台账仍写 `last_status="ok"` / `last_error=null` / `last_delivery_ok=true`。

根因：调用点只读 `result["error"]`，但 402/empty_response 走**主返回**路径，
携带的是 **`failed=True`**（agent_mixin 早已透传）—— **信号存在，没人看**。

本文件三条「新形态必须绿」+ 一条「旧形态必然假绿」的**对照臂** + 一条**接线守卫**。
"""
from __future__ import annotations

import pathlib
import sys

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from gateway.cron_mixin import cron_run_outcome  # noqa: E402

FAULT_NOTICE = (
    "[故障明示] 我这轮没调到模型（连续错误），请让我重启或查看日志"
    "——故障已记录，不会伪装成正常回复"
)


def _legacy_outcome(result):
    """修复前的判据（逐字复刻）：只看 ``result["error"]``。

    它的存在是为了让「旧形态在这些坏样本上会记 ok」成为**可断言的事实**，
    而不是散文里的祈使句。
    """
    if result.get("error"):
        return "error", str(result.get("error"))
    return "ok", None


# ── 坏样本：新形态必须 error ────────────────────────────────────────────────
def test_402_empty_response_now_marks_error():
    """402 异常退出：failure 信号在 failed，不在 error。"""
    r = {"final_response": FAULT_NOTICE, "failed": True}
    assert cron_run_outcome(r)[0] == "error"


def test_billing_exhausted_reason_is_recorded():
    r = {"final_response": "[断粮] …", "failed": True, "exit_reason": "billing_exhausted"}
    status, err = cron_run_outcome(r)
    assert status == "error"
    assert "billing_exhausted" in err


def test_abnormal_exit_reason_alone_is_enough():
    """没有 failed 键、只有异常 exit_reason（未来若只透传 exit_reason 也不漏）。"""
    status, err = cron_run_outcome({"final_response": "x", "exit_reason": "empty_response"})
    assert status == "error"
    assert "empty_response" in err


# ── 对照臂：旧形态在同一样本上「必然假绿」（假绿可复现，不是散文）──────────
def test_legacy_form_is_falsely_green_on_the_same_bad_sample():
    r = {"final_response": FAULT_NOTICE, "failed": True}
    assert _legacy_outcome(r) == ("ok", None)   # 旧形态：假绿（这就是事故现场）
    assert cron_run_outcome(r)[0] == "error"    # 新形态：对同样字节判 error


# ── 孪生臂：正常路径不得误伤 ────────────────────────────────────────────────
@pytest.mark.parametrize("r", [
    {"final_response": "索引健康 ✅ docs=20868 / 漂移 2 / 垃圾 0", "failed": False},
    {"final_response": "ok", "failed": False, "exit_reason": "natural"},
    {"final_response": "done"},                      # 旧契约：没有 failed 键
    {"failed": False, "exit_reason": "max_turns"},    # 非异常退出集
    {"failed": False, "exit_reason": ""},
])
def test_healthy_runs_stay_ok(r):
    assert cron_run_outcome(r) == ("ok", None)


# ── 回归：显式 error 的旧行为不得丢 ─────────────────────────────────────────
def test_explicit_error_still_wins():
    assert cron_run_outcome({"error": "boom", "failed": False}) == ("error", "boom")


def test_non_dict_is_safe():
    assert cron_run_outcome(None) == ("ok", None)


# ── 接线守卫：防止「修了纯函数但调用点被改回旧判据」────────────────────────
def test_call_site_actually_uses_the_helper():
    """源码级接线守卫（不是行为测试）。

    理由：本缺陷的形态就是「**助手存在但没人调**」——只测纯函数会让
    「回退调用点」静默变绿。故此处显式钉住调用点文本。
    """
    src = (REPO_ROOT / "gateway" / "cron_mixin.py").read_text(encoding="utf-8")
    assert "_status, _err = cron_run_outcome(result)" in src
    assert 'if result.get("error"):\n                        mark_job_run' not in src
