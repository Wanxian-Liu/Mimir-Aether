"""R1 四点（第 3 批）：探针丢字段 / 阶段混同 / 无条件降级 / 降级不可自愈。

不需要真 chroma：`probe()` 的子进程行为用 fake `subprocess.run` 喂读数，
判据阶梯（`classify` / `startup_action`）是纯函数，逐格验。
"""
from __future__ import annotations

import json
import subprocess

import pytest

import tools.chroma_guard as guard
from tools.chroma_session_indexer import DEFAULT_WRITE_LOCK_TIMEOUT_S


class _CP:
    def __init__(self, rc: int = 0, out: str = "", err: str = ""):
        self.returncode, self.stdout, self.stderr = rc, out, err


def _patch_run(monkeypatch, *, cp=None, exc=None):
    def fake(*_a, **_k):
        if exc is not None:
            raise exc
        return cp

    monkeypatch.setattr(guard.subprocess, "run", fake)


def _payload(**kv):
    base = {"ok": False, "stage": "count", "lock": "ok", "error": "boom"}
    base.update(kv)
    return _CP(out=json.dumps(base))


# --------------------------------------------------------------- 预算 > 锁预算
def test_probe_budget_exceeds_lock_budget():
    """20s < 60s 时，一次「忙但健康」的长写会被判成坏库。预算必须大于锁预算。"""
    assert guard._DEFAULT_TIMEOUT > DEFAULT_WRITE_LOCK_TIMEOUT_S


# ------------------------------------------------------------- ① lock 字段不再丢
def test_probe_keeps_lock_field(monkeypatch):
    _patch_run(monkeypatch, cp=_payload(stage="lock_import", lock="unavailable",
                                        error="lock_import: ImportError: x"))
    r = guard.probe()
    assert r["lock"] == "unavailable", "lock 字段又被丢掉了"
    assert r["classification"] == "lock_missing"
    assert guard.startup_action(r) == "startup_lock_unavailable"


def test_probe_ok_reports_lock(monkeypatch):
    _patch_run(monkeypatch, cp=_payload(ok=True, stage="get", count=7, lock="ok", error=None))
    r = guard.probe()
    assert (r["ok"], r["lock"], r["count"], r["classification"]) == (True, "ok", 7, "ok")
    assert guard.startup_action(r) is None


# ------------------------------------------------- ② 阶段自成一档（不许混同）
@pytest.mark.parametrize("stage,expected", [
    ("import", "chroma_import"),
    ("lock_import", "lock_missing"),
    ("open", "store_error"),
    ("count", "store_error"),
    ("get", "store_error"),
])
def test_stage_is_own_class(monkeypatch, stage, expected):
    _patch_run(monkeypatch, cp=_payload(stage=stage))
    assert guard.probe()["classification"] == expected


# ---------------------------------------------------- ③ 没有结论就不置降级
def test_timeout_is_inconclusive(monkeypatch):
    """核心负控：超时只说明「没等到」，不说明「库坏了」。"""
    _patch_run(monkeypatch, exc=subprocess.TimeoutExpired(cmd="probe", timeout=90))
    r = guard.probe()
    assert r["stage"] == "timeout"
    assert r["classification"] == "inconclusive"
    assert guard.startup_action(r) is None, "超时不许写降级标记"


def test_spawn_failure_is_inconclusive(monkeypatch):
    _patch_run(monkeypatch, exc=OSError("no such executable"))
    assert guard.startup_action(guard.probe()) is None


def test_child_rc1_is_inconclusive(monkeypatch):
    _patch_run(monkeypatch, cp=_CP(rc=1, err="Traceback: whatever"))
    r = guard.probe()
    assert r["stage"] == "child_crash" and r["segv"] is False
    assert guard.startup_action(r) is None


def test_unparsable_output_is_inconclusive(monkeypatch):
    _patch_run(monkeypatch, cp=_CP(out="not json"))
    assert guard.startup_action(guard.probe()) is None


def test_segv_marks_degraded(monkeypatch):
    _patch_run(monkeypatch, cp=_CP(rc=-11, err="segfault"))
    r = guard.probe()
    assert r["segv"] is True and r["classification"] == "segv"
    assert guard.startup_action(r) == "startup_probe_segv"


@pytest.mark.parametrize("classification,reason", [
    ("segv", "startup_probe_segv"),
    ("store_error", "startup_probe_failed"),
    ("chroma_import", "startup_chroma_import_failed"),
    ("lock_missing", "startup_lock_unavailable"),
    ("inconclusive", None),
    ("ok", None),
])
def test_startup_action_table(classification, reason):
    assert guard.startup_action({"classification": classification}) == reason


# --------------------------------------------------------- ④ 降级必须能自愈
def test_clear_degraded_recovers_and_keeps_outage(monkeypatch, tmp_path):
    monkeypatch.setenv("MIMIR_CHROMA_DEGRADE_STATE_PATH", str(tmp_path / "deg.json"))
    assert guard.chroma_usable() is True            # 无标记 = 可用

    guard.mark_degraded("startup_probe_failed", detail="count: DatabaseError")
    assert guard.chroma_usable() is False

    rec = guard.clear_degraded()
    assert rec["degraded"] is False and rec["prev_reason"] == "startup_probe_failed"
    assert rec.get("outage_s") is not None and rec["outage_s"] >= 0
    assert guard.chroma_usable() is True, "撤销后必须立刻回到 chroma"


def test_clear_degraded_without_prior_state_has_no_prev(monkeypatch, tmp_path):
    monkeypatch.setenv("MIMIR_CHROMA_DEGRADE_STATE_PATH", str(tmp_path / "deg.json"))
    rec = guard.clear_degraded()
    assert rec == {"degraded": False, "reason": "probe_ok", "since": rec["since"]}


# ------------------------------------------------------------------ 界面契约
def test_probe_result_keys(monkeypatch):
    """读数面就是契约：少一个键，看读数的人就少一个判据。"""
    _patch_run(monkeypatch, cp=_payload())
    r = guard.probe()
    assert {"ok", "count", "stage", "error", "lock", "rc", "elapsed_s",
            "segv", "classification"} <= set(r)
