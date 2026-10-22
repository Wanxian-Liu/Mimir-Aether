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
    ("lock_wait", "inconclusive"),   # F4（第 3 批）：等锁超时自成一档，不是 store_error

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


# ------------------------------------- ⑤ F1/F4（第 3 批）：lock 是状态，不是装饰
def test_import_failure_leaves_lock_unchecked(monkeypatch):
    """chromadb 导不进来 ⇒ 根本没走到验锁，``lock`` 不许写成 ``ok``。

    F1 负控：旧代码初值就是 ``"ok"``，于是「没验锁」和「锁住了」在读数上逐字同形。
    """
    _patch_run(monkeypatch, cp=_payload(stage="import", lock="unchecked",
                                       error="import: ModuleNotFoundError: chromadb"))
    r = guard.probe()
    assert r["lock"] == "unchecked" and r["lock"] != "ok", "没验锁却报 ok = 把「没验」读成「验过了」"
    assert r["classification"] == "chroma_import"


def test_lock_wait_timeout_is_inconclusive_not_store_error(monkeypatch):
    """F4 负控（读数面）：等锁超时 ≠ 库坏——store_error 会顺着 startup_action 落降级。"""
    _patch_run(monkeypatch, cp=_payload(
        stage="lock_wait", lock="timeout",
        error="lock_wait: ChromaWriteLockTimeout: chroma write lock not acquired within 1.0s"))
    r = guard.probe()
    assert r["lock"] == "timeout"
    assert "ChromaWriteLockTimeout" in r["error"], "error 必须带类名，否则读者分不清是锁还是库"
    assert r["classification"] == "inconclusive"
    assert r["classification"] != "store_error"
    assert guard.startup_action(r) is None, "等锁超时不许落降级（一次繁忙 = 永久 FTS5）"


def test_lock_timeout_without_stage_is_still_inconclusive():
    """stage 丢了也不能翻案：锁状态 timeout 单独就足以证明「没有结论」。"""
    assert guard.classify({"ok": False, "lock": "timeout", "stage": None}) == "inconclusive"
    assert guard.startup_action({"ok": False, "lock": "timeout"}) is None


@pytest.mark.parametrize("lock,stage,expected", [
    ("ok", "count", "store_error"),        # 真取到锁后开库/计数失败 ⇒ 库确实有问题
    ("unchecked", "import", "chroma_import"),
    ("unavailable", "lock_import", "lock_missing"),
])
def test_lock_field_semantics(monkeypatch, lock, stage, expected):
    """F1：四态各自对应一档分类，任何格都不许退化成 ``ok``。"""
    _patch_run(monkeypatch, cp=_payload(lock=lock, stage=stage))
    r = guard.probe()
    assert r["lock"] == lock
    assert r["classification"] == expected


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


# ------------------------------- F4b 持锁后开库失败 = 真故障（刘哥 2026-10-22 更正）
def test_lock_acquired_then_store_open_fails_is_store_error(monkeypatch):
    """正控：锁真取到（lock=ok）但库打不开 ⇒ store_error，**不许** inconclusive。

    旧行为（本轮修掉的）：持锁成功后 stage 仍停在 "lock_wait" ⇒ classify 判
    inconclusive ⇒ startup_action 返 None ⇒ 不落降级 ⇒ 真故障（损坏 / 无权限 /
    磁盘满）被静默。这是把「忙→坏」的假阳换成了「坏→判不了」的假阴。

    判据只锚**行为**（lock=ok ⇒ 已持锁 ⇒ 开库失败必须是 store_error），不锚档名
    ——档名可以改，语义不许回退。
    """
    _patch_run(monkeypatch, cp=_payload(stage="open", lock="ok",
                                        error="RuntimeError: disk full"))
    r = guard.probe()
    assert r["lock"] == "ok" and r["stage"] != "lock_wait", r
    assert r["classification"] == "store_error", r
    assert guard.startup_action(r) == "startup_probe_failed", r


def test_classify_lock_wait_stays_inconclusive():
    """负控（同族不许翻案）：等锁阶段仍是 inconclusive —— 忙只证明忙。"""
    for r in ({"ok": False, "stage": "lock_wait", "lock": "timeout"},
              {"ok": False, "stage": "lock_wait", "lock": "unchecked"}):
        assert guard.classify(r) == "inconclusive", r
        assert guard.startup_action(r) is None, r


def test_probe_holds_lock_then_store_open_fails(monkeypatch, tmp_path):
    """端到端（真子进程 + 真跨进程锁 + 假 chromadb）：

    持锁成功、``PersistentClient()`` 抛错 ⇒ 读数 lock="ok" + stage 已离场 lock_wait
    ⇒ classify=store_error ⇒ 落降级。顺带验 F5：账本被 MIMIR_CHROMA_EVENTS_FILE
    指到 tmp（写端真读 env），事件不落生产账本。
    """
    fake = tmp_path / "fakelib"
    fake.mkdir()
    (fake / "chromadb.py").write_text(
        "class PersistentClient:\n"
        "    def __init__(self, *a, **k):\n"
        "        raise RuntimeError('disk full: cannot open sqlite')\n",
        encoding="utf-8",
    )
    ledger = tmp_path / "events.jsonl"
    monkeypatch.setenv("PYTHONPATH", str(fake))
    monkeypatch.setenv("MIMIR_CHROMA_EVENTS_FILE", str(ledger))

    r = guard.probe(timeout_s=90)
    assert r["ok"] is False
    assert r["lock"] == "ok", r          # 锁真的取到了（不是猜的）
    assert r["stage"] != "lock_wait", r   # 持锁后开库失败=真故障，不许留在等待档
    assert r["rc"] == 0, r
    assert r["classification"] == "store_error", r
    assert guard.startup_action(r) == "startup_probe_failed", r

    # F5 写端：env 真把账本指走了
    assert ledger.exists(), "MIMIR_CHROMA_EVENTS_FILE 未生效（账本没被指走）"
    text = ledger.read_text(encoding="utf-8")
    assert '"role":"probe"' in text, text[:400]
