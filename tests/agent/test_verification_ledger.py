"""R2 量具缺失修复测试 —— `data/verification_results.jsonl` 生产端 + 显式 N/A 读口。

R2 病灶（总表 2026-09-18 行 298）：`data/verification_results.jsonl` **从未被创建**（0 写端），
而既有读端写着 `if not log_path.exists(): return 0 / {"total": 0}`
⇒ **「无数据」被伪装成「无失败」**（假绿）。

本测试钉住四条不变量：
  ① **生产端真落盘**：守卫**真的判过**且本轮出现声明 ⇒ 追加一条记录（有声明才记 = 防刷量）；
  ② **无数据 ⇒ 显式 N/A**：`status="no_data"` / `n_a=True` / `total is None`（**不是 0**）
     + WARNING —— **负控**：删掉文件跑技能，必须显式 N/A，不许静默 0（R2 DoD 原文）；
  ③ **纯加法/守卫语义不变量**：`evaluate_finish()` 返回值与 `should_block_finish()` 逐位相同，
     量具写失败/停写都不影响守卫判定；
  ④ **路径不做 HOME 嵌套**：落盘路径来自 `get_mimir_home()`，不允许 `~/.mimiraether/.mimiraether/…`。
"""
from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from agent import probe_attest as _probe_attest  # noqa: E402
from agent.verification_ledger import (  # noqa: E402
    NO_DATA_SEMANTICS,
    ledger_path,
    read_ledger_status,
    record_verification_result,
    repeat_tool_calls,
    verification_failure_stats,
    verification_reliability,
)
from agent.verify_before_report_guard import (  # noqa: E402
    evaluate_finish,
    should_block_finish,
)

FAIL_TYPE_CLAIM = "claim_without_verification"
FAIL_TYPE_PROBE = "probe_attest_unverified"


# ===========================================================================
# fixtures
# ===========================================================================

@pytest.fixture()
def ledger(tmp_path, monkeypatch) -> Path:
    """量具落点隔离到 tmp（绝不写生产 data/）。"""
    path = tmp_path / "data" / "verification_results.jsonl"
    monkeypatch.setenv("MIMIR_VERIFICATION_RESULTS_PATH", str(path))
    monkeypatch.setenv("MIMIR_VERIFICATION_LEDGER", "1")
    monkeypatch.setenv("MIMIR_VERIFY_BEFORE_REPORT", "1")
    return path


@pytest.fixture()
def no_probe_gate(monkeypatch):
    """把 RS17 探针闸置为「不干预」，隔离出 verify-before-report 自身的判定分支。"""
    monkeypatch.setattr(_probe_attest, "evaluate_turn", lambda *a, **k: None)


def _lines(path: Path) -> list[dict]:
    return [json.loads(s) for s in path.read_text(encoding="utf-8").splitlines() if s.strip()]


def _msgs(user: str, assistant_text: str, tool: str | None = None) -> list[dict]:
    msgs: list[dict] = [{"role": "user", "content": user}]
    if tool:
        msgs.append({
            "role": "assistant",
            "content": assistant_text,
            "tool_calls": [{
                "id": "call_1",
                "type": "function",
                "function": {"name": tool, "arguments": "{}"},
            }],
        })
    else:
        msgs.append({"role": "assistant", "content": assistant_text})
    return msgs


# ===========================================================================
# ① 生产端
# ===========================================================================

def test_producer_creates_ledger_with_compatible_schema(ledger: Path) -> None:
    """生产端首次落盘会自建目录+文件；schema 与既有读端逐键兼容。"""
    assert not ledger.exists()
    record_verification_result(passed=False, failure_type=FAIL_TYPE_CLAIM,
                               message="claim 无验证调用", claim="已完成", user="用户")
    record_verification_result(passed=True, tool="read_file")
    assert ledger.exists()

    rows = _lines(ledger)
    assert len(rows) == 2
    for row in rows:
        assert {"timestamp", "passed", "failure_type", "tool", "message", "source"} <= set(row)
    assert rows[0]["passed"] is False
    assert rows[0]["failure_type"] == FAIL_TYPE_CLAIM
    assert rows[1]["passed"] is True
    assert rows[1]["tool"] == "read_file"
    assert all(r.get("timestamp") for r in rows)


def test_producer_never_raises_on_bad_path(monkeypatch, tmp_path) -> None:
    """纯加法：落盘失败只 WARNING，不抛（守卫语义不变量）。"""
    monkeypatch.setenv("MIMIR_VERIFICATION_RESULTS_PATH", str(tmp_path))  # 目录当文件 → 必失败
    assert record_verification_result(passed=False, failure_type="x") is None


def test_producer_disabled_by_env(ledger: Path, monkeypatch) -> None:
    """MIMIR_VERIFICATION_LEDGER=0 ⇒ 停写（量具可关，读口语义不变）。"""
    monkeypatch.setenv("MIMIR_VERIFICATION_LEDGER", "0")
    assert record_verification_result(passed=False, failure_type="x") is None
    assert not ledger.exists()


def test_ledger_path_is_not_home_nested(tmp_path, monkeypatch) -> None:
    """路径真源 = get_mimir_home()：不得产出 `…/.mimiraether/.mimiraether/…` 嵌套假路径。"""
    monkeypatch.delenv("MIMIR_VERIFICATION_RESULTS_PATH", raising=False)
    monkeypatch.setenv("MIMIR_AETHER_HOME", str(tmp_path))
    p = ledger_path()
    assert str(p).startswith(str(tmp_path))
    assert str(tmp_path) + "/.mimiraether/.mimiraether" not in str(p)
    assert p.name == "verification_results.jsonl"


# ===========================================================================
# ② 读口：有数据 ⇒ 真读数
# ===========================================================================

def test_reader_counts_failures_by_type(ledger: Path) -> None:
    record_verification_result(passed=False, failure_type=FAIL_TYPE_CLAIM)
    record_verification_result(passed=False, failure_type="write_claim_without_write_action")
    record_verification_result(passed=False, failure_type=FAIL_TYPE_CLAIM)
    record_verification_result(passed=True, tool="read_file")

    stats = verification_failure_stats()
    assert stats["status"] == "ok"
    assert stats["n_a"] is False
    assert stats["total"] == 3
    assert stats["by_type"] == {
        FAIL_TYPE_CLAIM: 2,
        "write_claim_without_write_action": 1,
    }
    assert stats["samples"] == 4


def test_repeat_tool_calls_with_data(ledger: Path) -> None:
    for _ in range(2):
        record_verification_result(passed=True, tool="read_file")
    record_verification_result(passed=True, tool="search_files")
    rep = repeat_tool_calls()
    assert rep["status"] == "ok"
    assert rep["max_repeat"] == 2
    assert rep["by_tool"] == {"read_file": 2, "search_files": 1}


def test_reliability_with_data(ledger: Path) -> None:
    record_verification_result(passed=True, tool="read_file")
    record_verification_result(passed=False, failure_type=FAIL_TYPE_CLAIM)
    rel = verification_reliability()
    assert rel["status"] == "ok"
    assert rel["n_a"] is False
    assert 0.0 < rel["reliability_score"] < 1.0
    assert rel["sample_quality"] == "low"
    assert rel["total_samples"] == 2


# ===========================================================================
# ② 负控：无数据 ⇒ 显式 N/A（**绝不是 0**）
# ===========================================================================

def test_negative_control_missing_file_is_na_not_zero(ledger: Path) -> None:
    """负控（R2 DoD 原文）：删掉/缺失文件跑技能，必须显式 N/A，不许静默 0。"""
    assert not ledger.exists()
    status = read_ledger_status()
    assert status["status"] == "no_data"
    assert status["n_a"] is True
    assert status["exists"] is False
    assert status["semantics"] == NO_DATA_SEMANTICS

    stats = verification_failure_stats()
    assert stats["status"] == "no_data"
    assert stats["n_a"] is True
    assert stats["total"] is None            # ← 核心：不是 0
    assert stats["total"] != 0
    assert stats["by_type"] is None
    assert "量具缺失" in stats["reason"]

    rep = repeat_tool_calls()
    assert rep["max_repeat"] is None         # ← 不是 0
    rel = verification_reliability()
    assert rel["reliability_score"] is None  # ← 不是伪造的 0.5
    assert rel["sample_quality"] == "n/a"


def test_negative_control_empty_file_is_na_not_zero(ledger: Path) -> None:
    """空文件 ≠ 零失败（同族假绿：文件在但无数据）。"""
    ledger.parent.mkdir(parents=True, exist_ok=True)
    ledger.write_text("", encoding="utf-8")
    status = read_ledger_status()
    assert status["exists"] is True
    assert status["status"] == "no_data"
    assert status["n_a"] is True
    assert verification_failure_stats()["total"] is None


def test_negative_control_missing_file_warns(caplog, ledger: Path) -> None:
    """缺失必须**出声**（WARNING 含「无数据 ≠ 无失败」），不许静默。"""
    with caplog.at_level(logging.WARNING, logger="agent.verification_ledger"):
        verification_failure_stats()
    assert any("无数据 ≠ 无失败" in rec.getMessage() for rec in caplog.records)


def test_corrupt_lines_are_counted_not_swallowed(ledger: Path) -> None:
    """坏行被计数（corrupt>0），有效行照常统计。"""
    ledger.parent.mkdir(parents=True, exist_ok=True)
    good = json.dumps({"timestamp": "t", "passed": False, "failure_type": FAIL_TYPE_CLAIM},
                      ensure_ascii=False)
    ledger.write_text(good + "\n{not json}\n[]\n", encoding="utf-8")
    status = read_ledger_status()
    assert status["status"] == "ok"
    assert status["valid"] == 1
    assert status["corrupt"] == 2
    assert verification_failure_stats()["total"] == 1


def test_all_corrupt_is_na_not_zero(ledger: Path) -> None:
    """全损坏 = 无可用数据 ⇒ N/A（不得读作 0 失败）。"""
    ledger.parent.mkdir(parents=True, exist_ok=True)
    ledger.write_text("{oops}\n{oops2}\n", encoding="utf-8")
    status = read_ledger_status()
    assert status["status"] == "no_data"
    assert status["n_a"] is True
    assert status["corrupt"] == 2
    assert verification_failure_stats()["total"] is None


# ===========================================================================
# ③ 守卫接线：真实判定 ⇒ 落盘（生产端活体路径）
# ===========================================================================

def test_guard_block_writes_failure_record(ledger: Path, no_probe_gate) -> None:
    """claim 无验证 ⇒ 守卫拦截 + 量具记 passed=False。"""
    text = "已完成修复，测试全绿。"
    msgs = _msgs("看看压缩阈值", text)
    assert evaluate_finish(msgs, text) is True

    rows = _lines(ledger)
    assert len(rows) == 1
    assert rows[0]["passed"] is False
    assert rows[0]["failure_type"] == FAIL_TYPE_CLAIM
    assert rows[0]["source"] == "verify_before_report_guard"
    assert "已完成" in rows[0]["message"]


def test_guard_pass_writes_passed_record(ledger: Path, no_probe_gate) -> None:
    """claim + 本轮有验证工具调用 ⇒ 放行 + 量具记 passed=True（带 tool）。"""
    text = "已完成检查。"
    msgs = _msgs("看看压缩阈值", text, tool="read_file")
    assert evaluate_finish(msgs, text) is False

    rows = _lines(ledger)
    assert len(rows) == 1
    assert rows[0]["passed"] is True
    assert rows[0]["failure_type"] is None
    assert rows[0]["tool"] == "read_file"


def test_guard_no_claim_no_record(ledger: Path, no_probe_gate) -> None:
    """无声明、无拦截 ⇒ 不落盘（防刷量：量具只记「出现声明的判定」）。"""
    text = "读了一下，阈值是 120000。"
    msgs = _msgs("看看压缩阈值", text)
    assert evaluate_finish(msgs, text) is False
    assert not ledger.exists()


def test_guard_probe_block_is_recorded(ledger: Path, monkeypatch) -> None:
    """RS17 探针闸拦截也要进量具（failure_type=probe_attest_unverified）。"""
    monkeypatch.setattr(_probe_attest, "evaluate_turn",
                        lambda *a, **k: {"blocked": True, "claims": ["缺失"], "mode": "hard"})
    text = "该文件缺失。"
    msgs = _msgs("看看压缩阈值", text)
    assert evaluate_finish(msgs, text) is True
    rows = _lines(ledger)
    assert rows[-1]["passed"] is False
    assert rows[-1]["failure_type"] == FAIL_TYPE_PROBE


def test_guard_disabled_records_nothing(ledger: Path, no_probe_gate, monkeypatch) -> None:
    """守卫全局关闭 ⇒ 未判定 ⇒ 不落盘（防把「没判」记成「判过且通过」）。"""
    monkeypatch.setenv("MIMIR_VERIFY_BEFORE_REPORT", "0")
    text = "已完成修复。"
    msgs = _msgs("看看压缩阈值", text)
    assert evaluate_finish(msgs, text) is False
    assert not ledger.exists()


# ===========================================================================
# ③ 纯加法：evaluate_finish 与 should_block_finish 逐位同值
# ===========================================================================

@pytest.mark.parametrize("text,tool", [
    ("已完成修复，测试全绿。", None),
    ("已完成检查。", "read_file"),
    ("读了一下，阈值是 120000。", None),
    ("收到——补上写盘交付物", None),
    ("今天压缩未生效，result 为 0", None),
])
def test_evaluate_finish_matches_legacy_predicate(ledger: Path, no_probe_gate, text, tool) -> None:
    """R2 纯加法：新入口返回值 == 旧谓词返回值（逐位相同，量具不改变守卫语义）。"""
    legacy = should_block_finish(_msgs("看看压缩阈值", text, tool=tool), text)
    new = evaluate_finish(_msgs("看看压缩阈值", text, tool=tool), text)
    assert new is legacy


def test_evaluate_finish_survives_broken_ledger(ledger: Path, no_probe_gate, monkeypatch) -> None:
    """量具坏（不可写路径）⇒ 守卫判定不受影响（fail-open：被观测对象优先）。"""
    monkeypatch.setenv("MIMIR_VERIFICATION_RESULTS_PATH", "/")
    text = "已完成修复，测试全绿。"
    assert evaluate_finish(_msgs("看看压缩阈值", text), text) is True
