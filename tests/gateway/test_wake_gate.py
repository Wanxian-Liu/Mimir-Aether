"""U13 单飞闸用例基线（U11 组件）—— ≥20 用例，纯逻辑，无 IO/无网络。

判据真源：~/.mimiraether/notes/2026-09-13-U11-wake-gate-design.md（§用例矩阵）
运行：.venv/bin/python3 -m pytest tests/gateway/test_wake_gate.py -q
"""

from __future__ import annotations

import os
import sys
import threading
import time

import pytest

_REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

from gateway.wake_gate import (  # noqa: E402
    DEFAULT_DEDUP_WINDOW_S,
    DEFAULT_LEASE_S,
    GATE_ENV,
    REASONS,
    WakeGate,
    event_fingerprint,
    gate_enabled,
    get_wake_gate,
    reset_wake_gate,
    wake_gate_snapshot,
)

SK = "feishu:chat-1"


def mk(env=None, lease_s=60.0, dedup_window_s=900.0, max_fingerprints=4096):
    """测试用闸门：可控时钟 + 可控 env。"""
    box = {"now": 1000.0}
    return (
        WakeGate(
            lease_s=lease_s,
            dedup_window_s=dedup_window_s,
            clock=lambda: box["now"],
            env_getter=lambda: (env or {}),
            max_fingerprints=max_fingerprints,
        ),
        box,
    )


# -- 1..4 基本取锁/释放 -----------------------------------------------------


def test_grant_first_wake():
    g, _ = mk()
    d = g.acquire(SK, "runA", "api_direct")
    assert d.granted is True and d.reason == "granted"
    assert g.active_holders()[SK].run_token == "runA"


def test_second_wake_same_session_rejected_occupied():
    g, box = mk()
    g.acquire(SK, "runA", "api_direct")
    box["now"] += 1
    d = g.acquire(SK, "runB", "buzz_template")
    assert d.granted is False and d.reason == "occupied"
    assert d.holder_trigger_source == "api_direct"
    assert g.active_holders()[SK].run_token == "runA"  # 未被顶替


def test_release_allows_reacquire():
    g, box = mk()
    g.acquire(SK, "runA")
    assert g.release(SK, "runA") is True
    box["now"] += 1
    d = g.acquire(SK, "runB", fingerprint=event_fingerprint("other"))
    assert d.granted is True


def test_release_with_wrong_token_is_noop():
    g, _ = mk()
    g.acquire(SK, "runA")
    assert g.release(SK, "runX") is False
    assert g.active_holders()[SK].run_token == "runA"


# -- 5..8 事件指纹去重（治双派） -------------------------------------------


def test_duplicate_fingerprint_after_release_rejected():
    g, box = mk()
    fp = event_fingerprint("wake-payload-1")
    g.acquire(SK, "runA", fingerprint=fp)
    g.release(SK, "runA")
    box["now"] += 5
    d = g.acquire(SK, "runB", fingerprint=fp)
    assert d.granted is False and d.reason == "duplicate_event"
    assert d.duplicate_of_run_token == "runA"


def test_fingerprint_after_window_allowed():
    g, box = mk()
    fp = event_fingerprint("wake-payload-1")
    g.acquire(SK, "runA", fingerprint=fp)
    g.release(SK, "runA")
    box["now"] += DEFAULT_DEDUP_WINDOW_S + 1
    d = g.acquire(SK, "runB", fingerprint=fp)
    assert d.granted is True and d.reason == "granted"


def test_occupied_takes_precedence_over_duplicate_fingerprint():
    g, box = mk()
    fp = event_fingerprint("same")
    g.acquire(SK, "runA", fingerprint=fp)
    box["now"] += 1
    d = g.acquire(SK, "runB", fingerprint=fp)
    assert d.reason == "occupied"  # 在位占用优先（更可操作的信号）


def test_distinct_fingerprints_do_not_collide():
    g, box = mk()
    g.acquire(SK, "runA", fingerprint=event_fingerprint("w1"))
    g.release(SK, "runA")
    box["now"] += 1
    assert g.acquire(SK, "runB", fingerprint=event_fingerprint("w2")).granted


# -- 9..12 交互消息与急停开关 ----------------------------------------------


def test_interactive_user_bypasses_occupied():
    g, box = mk()
    g.acquire(SK, "runA")
    box["now"] += 1
    d = g.acquire(SK, "user-run", "feishu", mode="user")
    assert d.granted is True and d.reason == "interactive_bypass"
    assert g.active_holders()[SK].run_token == "runA"  # 交互不抢锁


def test_interactive_does_not_create_holder():
    g, _ = mk()
    g.acquire(SK, "user-run", "feishu", mode="user")
    assert SK not in g.active_holders()


def test_kill_switch_off_grants_all():
    g, box = mk()
    g2, _ = mk(env={GATE_ENV: "off"})
    g.acquire(SK, "runA")
    box["now"] += 1
    d = g2.acquire(SK, "runB")
    assert d.granted is True and d.reason == "gate_off"
    assert g2.snapshot()["gate_off_total"] == 1


@pytest.mark.parametrize("val", ["off", "0", "false", "no", "disabled", "none", "OFF"])
def test_kill_switch_value_matrix(val):
    g, _ = mk(env={GATE_ENV: val})
    assert g.acquire(SK, "runA").reason == "gate_off"


def test_gate_enabled_defaults_true_and_helper():
    assert gate_enabled({}) is True
    assert gate_enabled({GATE_ENV: "on"}) is True
    assert gate_enabled({GATE_ENV: "off"}) is False
    assert DEFAULT_LEASE_S > 0 and DEFAULT_DEDUP_WINDOW_S == 900.0


# -- 13..16 租约（到期只报警不强夺） ---------------------------------------


def test_lease_expiry_does_not_steal():
    g, box = mk(lease_s=10.0)
    g.acquire(SK, "runA", "api_direct")
    box["now"] += 11
    d = g.acquire(SK, "runB", "buzz_template")
    assert d.granted is False and d.reason == "occupied_lease_expired"
    assert g.active_holders()[SK].run_token == "runA"  # 不强夺


def test_lease_expiry_counter_increments():
    g, box = mk(lease_s=10.0)
    g.acquire(SK, "runA")
    box["now"] += 11
    g.acquire(SK, "runB")
    snap = g.snapshot()
    assert snap["lease_expiry_reported_total"] == 1
    assert snap["run_rejected_by_gate_total"] == 1


def test_holder_remaining_reported():
    g, box = mk(lease_s=100.0)
    g.acquire(SK, "runA")
    box["now"] += 30
    d = g.acquire(SK, "runB")
    assert 69.0 <= d.holder_remaining_s <= 71.0


def test_receipt_texts():
    g, box = mk(lease_s=100.0)
    g.acquire(SK, "runA", "api_direct")
    box["now"] += 10
    r1 = g.acquire(SK, "runB").receipt()
    assert "runA" in r1 and "api_direct" in r1 and "剩余" in r1
    g.release(SK, "runA")
    fp = event_fingerprint("x")
    g.acquire(SK, "runC", fingerprint=fp)
    g.release(SK, "runC")
    r2 = g.acquire(SK, "runD", fingerprint=fp).receipt()
    assert "重复" in r2
    assert g.acquire("other", "runE").receipt().startswith("wake-gate: granted")


# -- 17..20 指标（U12） -----------------------------------------------------


def test_metrics_snapshot_keys():
    g, _ = mk()
    snap = g.snapshot()
    for k in (
        "wake_granted_total",
        "wake_duplicate_total",
        "run_rejected_by_gate_total",
        "run_concurrent_peak",
        "lease_expiry_reported_total",
        "gate_off_total",
        "interactive_bypass_total",
        "no_session_key_total",
        "active_runs",
        "holders",
        "gate_enabled",
    ):
        assert k in snap, k


def test_concurrent_peak_tracks_max_across_sessions():
    g, _ = mk()
    g.acquire("s1", "r1")
    g.acquire("s2", "r2")
    assert g.snapshot()["run_concurrent_peak"] == 2
    g.release("s1", "r1")
    g.acquire("s3", "r3")
    assert g.snapshot()["run_concurrent_peak"] == 2  # 峰值不减


def test_counters_granted_duplicate_rejected():
    g, box = mk()
    fp = event_fingerprint("p")
    g.acquire(SK, "r1", fingerprint=fp)
    g.release(SK, "r1")
    box["now"] += 1
    g.acquire(SK, "r2", fingerprint=fp)
    snap = g.snapshot()
    assert snap["wake_granted_total"] == 1
    assert snap["wake_duplicate_total"] == 1
    assert snap["run_rejected_by_gate_total"] == 1


def test_empty_session_key_bypass():
    g, _ = mk()
    d = g.acquire("", "runA")
    assert d.granted is True and d.reason == "no_session_key"
    assert g.snapshot()["no_session_key_total"] == 1


# -- 21..24 并发/等待 -------------------------------------------------------


def test_thread_safety_single_winner():
    g, _ = mk()
    results = []
    lock = threading.Lock()
    start = threading.Barrier(16)

    def worker(i):
        start.wait()
        d = g.acquire("concurrent-session", "run-%d" % i, "api")
        with lock:
            results.append(d)

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(16)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(results) == 16
    assert sum(1 for d in results if d.granted) == 1
    assert sum(1 for d in results if d.reason == "occupied") == 15


def test_wait_for_slot_succeeds_after_release():
    g, _ = mk()
    g.acquire(SK, "runA")

    def releaser():
        time.sleep(0.15)
        g.release(SK, "runA")

    threading.Thread(target=releaser).start()
    d = g.wait_for_slot(SK, timeout_s=3.0, run_token="runB", poll_s=0.02)
    assert d.granted is True


def test_wait_for_slot_timeout_returns_occupied():
    g, _ = mk()
    g.acquire(SK, "runA")
    t0 = time.time()
    d = g.wait_for_slot(SK, timeout_s=0.2, run_token="runB", poll_s=0.05)
    assert d.granted is False and d.reason == "occupied"
    assert time.time() - t0 < 3.0


def test_wait_for_slot_zero_timeout_never_blocks():
    g, _ = mk()
    g.acquire(SK, "runA")
    d = g.wait_for_slot(SK, timeout_s=0.0, run_token="runB")
    assert d.reason == "occupied"


# -- 25..29 指纹/复位/reason 集合/单例 -------------------------------------


def test_fingerprint_stable_and_16_hex():
    fp = event_fingerprint("a", "b")
    assert fp == event_fingerprint("a", "b")
    assert len(fp) == 16 and all(c in "0123456789abcdef" for c in fp)
    assert event_fingerprint("ab", "c") != event_fingerprint("a", "bc")


def test_fingerprint_pruning_bounds_memory():
    g, box = mk(dedup_window_s=10.0, max_fingerprints=5)
    for i in range(20):
        g.acquire(SK, "r%d" % i, fingerprint=event_fingerprint("f%d" % i))
        g.release(SK, "r%d" % i)
        box["now"] += 1
    assert len(g._fingerprints.get(SK, {})) <= 5  # noqa: SLF001


def test_reset_clears_state():
    g, _ = mk()
    g.acquire(SK, "runA")
    g.reset()
    assert g.active_holders() == {}
    assert g.snapshot()["wake_granted_total"] == 0
    assert g.acquire(SK, "runB").granted is True


def test_reasons_set_is_exhaustive():
    g, box = mk(lease_s=5.0)
    seen = {
        g.acquire(SK, "a").reason,
        g.acquire(SK, "b").reason,
        g.acquire(SK, "c", mode="user").reason,
        g.acquire("", "d").reason,
    }
    box["now"] += 6
    seen.add(g.acquire(SK, "e").reason)
    g.release(SK, "a")
    fp = event_fingerprint("dup")
    g.acquire(SK, "f", fingerprint=fp)
    g.release(SK, "f")
    seen.add(g.acquire(SK, "g", fingerprint=fp).reason)
    g_off, _ = mk(env={GATE_ENV: "off"})
    seen.add(g_off.acquire(SK, "h").reason)
    assert seen <= REASONS
    assert {"granted", "occupied", "interactive_bypass", "no_session_key"} <= seen


def test_module_singleton_helpers():
    reset_wake_gate()
    g = get_wake_gate()
    assert get_wake_gate() is g
    g.acquire("s", "r")
    snap = wake_gate_snapshot()
    assert snap["active_runs"] == 1
    reset_wake_gate()
    assert wake_gate_snapshot()["active_runs"] == 0
