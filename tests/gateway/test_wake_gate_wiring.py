"""RS1 接线集成用例（U11 · 四方裁决 2026-09-13）。

**打真实入口**：``gateway.wake_gate.acquire_for_run`` —— 即 ``run_sync()`` 唯一
收口点调用的唯一取锁入口（不是测试内的镜像实现）。

判据来源：U11 方案 §4「interrupt 三问 + 双派/急停」+ 四方裁决 CR2。

用例 ⇄ 判据对应：
  1 交互仍能打断（不占位）
  2 队列续轮不自锁（不调用 acquire）
  3 被拒唤醒确实回执 + 释放后锁归零
  4 双派同事件去重（指纹不随释放清除）
  5 急停可逆（gate_off）
  6 闸内部异常：自治 fail-closed / 交互放行（CR2 范围收窄）
"""
import pytest

from gateway import wake_gate as wg


@pytest.fixture(autouse=True)
def _clean_gate(monkeypatch):
    monkeypatch.delenv(wg.GATE_ENV, raising=False)
    wg.reset_wake_gate()
    yield
    wg.reset_wake_gate()


def _gate():
    return wg.get_wake_gate()


def test_1_interactive_does_not_occupy():
    """交互消息：放行且不占位 ⇒ 自主 run 仍持锁、用户消息可打断。"""
    d1 = wg.acquire_for_run(
        session_key="s", trigger_source="buzz-watcher", run_token="r1", message="m1"
    )
    assert d1 is not None and d1.granted and d1.reason == "granted"

    d2 = wg.acquire_for_run(
        session_key="s", trigger_source="feishu", run_token="r2", message="m2"
    )
    assert d2 is not None and d2.granted
    assert d2.reason == "interactive_bypass"

    holders = _gate().snapshot()["holders"]
    assert set(holders) == {"s"}
    assert holders["s"]["run_token"] == "r1", "交互 run 不得顶掉自主 run 的占位"

    _gate().release("s", "r1")
    assert _gate().snapshot()["holders"] == {}, "交互 run 不得留下占位（留了会掐死后续）"


def test_2_continuation_bypasses_acquire():
    """续轮（interrupt_depth>0）：完全不取锁 ⇒ 不自锁、指标不增。"""
    before = _gate().snapshot()
    d = wg.acquire_for_run(
        session_key="s",
        trigger_source="buzz-watcher",
        run_token="r2",
        message="m",
        interrupt_depth=1,
    )
    assert d is None, "续轮必须返回 None（调用方不释放）"
    after = _gate().snapshot()
    assert after["wake_granted_total"] == before["wake_granted_total"]
    assert after["run_rejected_by_gate_total"] == before["run_rejected_by_gate_total"]
    assert after["holders"] == {}


def test_2b_without_bypass_would_self_lock():
    """反证：同 session 持锁时再取（无续轮旁路）必被拒 —— 这正是自锁的形态。"""
    wg.acquire_for_run(
        session_key="s", trigger_source="buzz-watcher", run_token="r1", message="m1"
    )
    d = wg.acquire_for_run(
        session_key="s", trigger_source="buzz-watcher", run_token="r2", message="m2"
    )
    assert d is not None and not d.granted
    assert d.reason in {"occupied", "occupied_lease_expired"}


def test_3_denied_wake_returns_receipt_and_releases():
    """被拒唤醒：回执可见（不静默丢弃）；首 run 释放后锁归零。"""
    wg.acquire_for_run(
        session_key="s", trigger_source="buzz-watcher", run_token="r1", message="m1"
    )
    d = wg.acquire_for_run(
        session_key="s", trigger_source="buzz-watcher", run_token="r2", message="m2"
    )
    assert d is not None and not d.granted
    assert d.reason in {"occupied", "occupied_lease_expired"}
    assert "wake-gate" in d.receipt() and d.receipt().strip()

    assert _gate().release("s", "r1") is True
    assert _gate().snapshot()["active_runs"] == 0


def test_3b_release_with_wrong_token_is_refused():
    """run_token 不符不得释放（防误放他人锁）。"""
    wg.acquire_for_run(
        session_key="s", trigger_source="buzz-watcher", run_token="r1", message="m1"
    )
    assert _gate().release("s", "not-mine") is False
    assert _gate().snapshot()["active_runs"] == 1


def test_4_duplicate_event_dedup_survives_release():
    """双派同事件（同 session + 同指纹）：第二次判 duplicate_event，且释放不清指纹。"""
    d1 = wg.acquire_for_run(
        session_key="s", trigger_source="buzz-watcher", run_token="r1", message="same"
    )
    assert d1 is not None and d1.granted
    _gate().release("s", "r1")

    d2 = wg.acquire_for_run(
        session_key="s", trigger_source="buzz-watcher", run_token="r2", message="same"
    )
    assert d2 is not None and not d2.granted
    assert d2.reason == "duplicate_event"
    assert d2.duplicate_of_run_token == "r1"
    assert "wake-gate" in d2.receipt()


def test_4b_different_event_still_granted():
    """不同事件（指纹不同）不得被误判重复。"""
    wg.acquire_for_run(
        session_key="s", trigger_source="buzz-watcher", run_token="r1", message="event-A"
    )
    _gate().release("s", "r1")
    d = wg.acquire_for_run(
        session_key="s", trigger_source="buzz-watcher", run_token="r2", message="event-B"
    )
    assert d is not None and d.granted


def test_5_kill_switch_is_reversible(monkeypatch):
    """急停：MIMIR_WAKE_GATE=off ⇒ 全放行（可逆回滚位 CR4）。"""
    monkeypatch.setenv(wg.GATE_ENV, "off")
    d = wg.acquire_for_run(
        session_key="s", trigger_source="buzz-watcher", run_token="r1", message="m"
    )
    assert d is not None and d.granted and d.reason == "gate_off"

    monkeypatch.setenv(wg.GATE_ENV, "on")
    d2 = wg.acquire_for_run(
        session_key="s", trigger_source="buzz-watcher", run_token="r2", message="m2"
    )
    assert d2 is not None and d2.granted and d2.reason == "granted"


class _BoomGate(wg.WakeGate):
    """闸自身故障模拟：acquire 必抛（note_internal_error 走真实现）。"""

    def acquire(self, *a, **k):  # noqa: D102
        raise RuntimeError("gate exploded")


def test_6_internal_error_fail_closed_for_wake(monkeypatch):
    """CR2：闸故障 ⇒ 自治通路 fail-closed（拒 + 计数 + 回执），不得 fail-open。"""
    monkeypatch.setattr(wg, "_GATE", _BoomGate())
    d = wg.acquire_for_run(
        session_key="s", trigger_source="buzz-watcher", run_token="r1", message="m"
    )
    assert d is not None and not d.granted
    assert d.reason == "gate_internal_error"
    assert "wake-gate" in d.receipt()
    assert wg.get_wake_gate().snapshot()["gate_errors_total"] == 1


def test_6b_internal_error_passes_interactive(monkeypatch):
    """CR2：闸故障不得掐死交互通路（刘哥的消息优先于闸的完整性）。"""
    monkeypatch.setattr(wg, "_GATE", _BoomGate())
    d = wg.acquire_for_run(
        session_key="s", trigger_source="feishu", run_token="r1", message="m"
    )
    assert d is None, "交互通路遇闸故障应放行（None = 不持锁）"


def test_7_wake_sources_contract():
    """mode 判定源契约：自治源集合固定，裸 api/feishu 不在其中。"""
    assert wg.WAKE_TRIGGER_SOURCES == frozenset(
        {"buzz-watcher", "watchdog", "cron", "self-restart"}
    )
    assert "api" not in wg.WAKE_TRIGGER_SOURCES
    assert "feishu" not in wg.WAKE_TRIGGER_SOURCES
