"""gateway/wake_gate.py — 运行级单飞闸（U11）+ 指标快照（U12）。

设计真源/判据：~/.mimiraether/notes/2026-09-13-U11-wake-gate-design.md
本模块只含纯逻辑（仅 stdlib），不 import gateway.*，便于单测与后续接线。

核心设计三条（U11 明文 + 本仓实证）：

1. 作用域 = 仅自主唤醒（mode="wake"）。交互消息（mode="user"）一律放行且不占位
   —— 按 session_key 无条件加锁会掐死既有 interrupt 通路（用户新消息必须能
   打断在跑的 run）。这是刻意范围收窄（CR2 trade-off），不是遗漏。

2. 两重拒因：(1) occupied：同 session_key 已有在跑 run；(2) duplicate_event：
   同 session_key + 同事件指纹在 dedup_window_s 内再现 —— 治「同一唤醒被
   api 直投 + buzz 模板双派 run」（15 分钟窗口实证）。

3. 租约到期只报警不强夺（U11 明文）：holder 过期仍不授予，返回
   occupied_lease_expired 并计数，由调用方写可见告警。

急停开关（可逆，CR4）：env MIMIR_WAKE_GATE=off|0|false|no|disabled|none → 全放行。

线程安全：threading.Lock 只包 O(1) 段，锁内无 await/sleep/IO（对齐
gateway/run.py 的 _agent_cache_lock 先例：跨事件循环与线程池共享）。

跨进程：本模块只做进程内；跨进程由 gateway/status.py acquire_scoped_lock 负责，
且 identity 必须含 run token（同 PID 重入判定会放行，直接用等于假锁）。
"""

from __future__ import annotations

import hashlib
import os
import threading
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional

__all__ = [
    "DEFAULT_LEASE_S",
    "DEFAULT_DEDUP_WINDOW_S",
    "GATE_ENV",
    "REASONS",
    "GateDecision",
    "Holder",
    "WakeGate",
    "event_fingerprint",
    "gate_enabled",
    "get_wake_gate",
    "wake_gate_snapshot",
    "reset_wake_gate",
]

# 默认租约（秒）。U11 要求默认 = run 最大时限；本仓 run 上限为
# HERMES_MAX_ITERATIONS=90 轮量级，1h 是保守上界（且到期只报警不强夺）。
DEFAULT_LEASE_S = 3600.0

# 事件指纹去重窗口（秒）= 双派唤醒实证的 15 分钟。
DEFAULT_DEDUP_WINDOW_S = 900.0

# 急停开关 env 名。
GATE_ENV = "MIMIR_WAKE_GATE"

_OFF_VALUES = {"off", "0", "false", "no", "disabled", "none"}

# 决定性 reason 取值集合（调用方与测试按此断言，避免自由文本漂移）。
REASONS = frozenset(
    {
        "granted",
        "gate_off",
        "no_session_key",
        "interactive_bypass",
        "occupied",
        "occupied_lease_expired",
        "duplicate_event",
    }
)


def gate_enabled(env: Optional[Dict[str, str]] = None) -> bool:
    """闸门是否启用（默认启用；env 显式关闭才停用）。"""
    raw = (env or os.environ).get(GATE_ENV)
    if raw is None:
        return True
    return str(raw).strip().lower() not in _OFF_VALUES


def event_fingerprint(*parts: str) -> str:
    """事件身份指纹：等值输入必等值输出（稳定、短、非可逆）。

    仅用于「同一唤醒事件」判等，不作安全用途。带分隔符，防
    ("ab","c") 与 ("a","bc") 相撞。
    """
    h = hashlib.sha256()
    for p in parts:
        h.update(str(p or "").encode("utf-8", errors="replace"))
        h.update(b"\x1f")
    return h.hexdigest()[:16]


@dataclass
class Holder:
    """当前占用者（一个 session_key 至多一个）。"""

    run_token: str
    trigger_source: str
    session_key: str
    started_at: float
    lease_s: float

    def remaining_s(self, now: float) -> float:
        return max(0.0, self.started_at + self.lease_s - now)

    def expired(self, now: float) -> bool:
        return self.remaining_s(now) <= 0.0


@dataclass
class GateDecision:
    """闸门裁决（含回执所需全部字段，调用方不再算时间）。"""

    granted: bool
    reason: str
    session_key: str = ""
    run_token: str = ""
    holder: Optional[Holder] = None
    holder_remaining_s: float = 0.0
    holder_trigger_source: str = ""
    duplicate_of_run_token: str = ""

    def receipt(self) -> str:
        """人类可读回执（U11：取不到必须写可见日志并回执，不静默丢弃）。"""
        if self.granted:
            return "wake-gate: granted (reason=%s)" % self.reason
        if self.reason == "occupied" and self.holder is not None:
            return (
                "wake-gate: 被 %s 占用（trigger_source=%s，剩余 %.0fs）"
                % (
                    self.holder.run_token,
                    self.holder_trigger_source,
                    self.holder_remaining_s,
                )
            )
        if self.reason == "occupied_lease_expired" and self.holder is not None:
            return (
                "wake-gate: 被 %s 占用但租约已过期（trigger_source=%s，"
                "告警不复位：需上层处置，本闸不强夺）"
                % (self.holder.run_token, self.holder_trigger_source)
            )
        if self.reason == "duplicate_event":
            return (
                "wake-gate: 同事件重复派发（dedup window 内同 fingerprint），原 run=%s"
                % (self.duplicate_of_run_token or "unknown")
            )
        return "wake-gate: rejected (reason=%s)" % self.reason


class WakeGate:
    """进程内 per-session_key 单飞闸（带租约 + 事件指纹去重 + 指标）。"""

    def __init__(
        self,
        lease_s: float = DEFAULT_LEASE_S,
        dedup_window_s: float = DEFAULT_DEDUP_WINDOW_S,
        clock: Optional[Callable[[], float]] = None,
        env_getter: Optional[Callable[[], Dict[str, str]]] = None,
        max_fingerprints: int = 4096,
    ) -> None:
        self.lease_s = float(lease_s)
        self.dedup_window_s = float(dedup_window_s)
        self._clock = clock or time.monotonic
        self._env_getter = env_getter or (lambda: os.environ)
        self._max_fingerprints = int(max_fingerprints)
        self._lock = threading.Lock()
        self._holders: Dict[str, Holder] = {}
        # session_key -> {fingerprint: (run_token, seen_at)}
        self._fingerprints: Dict[str, Dict[str, Any]] = {}
        self._metrics: Dict[str, int] = {
            "wake_granted_total": 0,
            "wake_duplicate_total": 0,
            "run_rejected_by_gate_total": 0,
            "run_concurrent_peak": 0,
            "lease_expiry_reported_total": 0,
            "gate_off_total": 0,
            "interactive_bypass_total": 0,
            "no_session_key_total": 0,
        }

    # -- 取锁 -------------------------------------------------------------

    def acquire(
        self,
        session_key: str,
        run_token: str,
        trigger_source: str = "unknown",
        fingerprint: str = "",
        mode: str = "wake",
        now: Optional[float] = None,
    ) -> GateDecision:
        """尝试取锁。mode="user" 为交互消息（放行不占位）。"""
        now = self._clock() if now is None else now

        if not gate_enabled(self._env_getter()):
            with self._lock:
                self._metrics["gate_off_total"] += 1
            return GateDecision(True, "gate_off", session_key, run_token)

        if not session_key:
            with self._lock:
                self._metrics["no_session_key_total"] += 1
            return GateDecision(True, "no_session_key", session_key, run_token)

        if mode == "user":
            with self._lock:
                self._metrics["interactive_bypass_total"] += 1
            return GateDecision(True, "interactive_bypass", session_key, run_token)

        with self._lock:
            self._prune_fingerprints_locked(session_key, now)
            holder = self._holders.get(session_key)
            if holder is not None:
                remaining = holder.remaining_s(now)
                decision = GateDecision(
                    granted=False,
                    reason="occupied" if remaining > 0 else "occupied_lease_expired",
                    session_key=session_key,
                    run_token=run_token,
                    holder=holder,
                    holder_remaining_s=remaining,
                    holder_trigger_source=holder.trigger_source,
                )
                if decision.reason == "occupied_lease_expired":
                    self._metrics["lease_expiry_reported_total"] += 1
                    self._metrics["run_rejected_by_gate_total"] += 1
                return decision

            dup_token = ""
            if fingerprint:
                seen = self._fingerprints.get(session_key, {}).get(fingerprint)
                if seen is not None and (now - seen[1]) <= self.dedup_window_s:
                    dup_token = seen[0]
            if dup_token:
                self._metrics["wake_duplicate_total"] += 1
                self._metrics["run_rejected_by_gate_total"] += 1
                return GateDecision(
                    False,
                    "duplicate_event",
                    session_key,
                    run_token,
                    duplicate_of_run_token=dup_token,
                )

            self._holders[session_key] = Holder(
                run_token=run_token,
                trigger_source=trigger_source,
                session_key=session_key,
                started_at=now,
                lease_s=self.lease_s,
            )
            if fingerprint:
                self._fingerprints.setdefault(session_key, {})[fingerprint] = (
                    run_token,
                    now,
                )
                # 插入后**再**收敛一次：剪枝在上方是「插入前」跑的，若只跑那一次，
                # 上界不变式 len <= max_fingerprints 会**恒超 1**（prune→insert 顺序问题，
                # 2026-09-13 由用例 27 抓到）。此调用幂等、O(窗口内条目数)。
                self._prune_fingerprints_locked(session_key, now)
            self._metrics["wake_granted_total"] += 1
            active = len(self._holders)
            if active > self._metrics["run_concurrent_peak"]:
                self._metrics["run_concurrent_peak"] = active
            return GateDecision(True, "granted", session_key, run_token)

    # -- 释放 -------------------------------------------------------------

    def release(self, session_key: str, run_token: str) -> bool:
        """显式释放。run_token 不匹配则不释放（防误放他人锁）。"""
        with self._lock:
            holder = self._holders.get(session_key)
            if holder is None or holder.run_token != run_token:
                return False
            del self._holders[session_key]
            return True

    def wait_for_slot(
        self,
        session_key: str,
        timeout_s: float,
        run_token: str = "",
        trigger_source: str = "unknown",
        fingerprint: str = "",
        poll_s: float = 0.05,
    ) -> GateDecision:
        """有界等待（U11：同 session 排队上限 = 1）。锁外轮询，无锁内 sleep。

        ⚠️ 等待期限必须用**真实墙钟**（``time.monotonic``），**不能**用可注入的
        业务时钟 ``self._clock``：单测注入冻结时钟时 deadline 永不到达 ⇒ 死循环
        （2026-09-13 实测踩坑：pytest 与直跑用例双双挂死 >200s，根因在此而非装置）。
        业务时钟仅用于租约/指纹窗口的判定，等待语义属真实时间。
        """
        if timeout_s <= 0:
            return self.acquire(
                session_key, run_token, trigger_source, fingerprint, mode="wake"
            )
        deadline = time.monotonic() + float(timeout_s)
        while True:
            decision = self.acquire(
                session_key, run_token, trigger_source, fingerprint, mode="wake"
            )
            if decision.granted or decision.reason != "occupied":
                return decision
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return decision
            time.sleep(min(poll_s, remaining))

    # -- 观测 -------------------------------------------------------------

    def snapshot(self) -> Dict[str, Any]:
        """U12 指标快照（/health 挂载用）。"""
        with self._lock:
            now = self._clock()
            holders = {
                k: {
                    "run_token": h.run_token,
                    "trigger_source": h.trigger_source,
                    "remaining_s": round(h.remaining_s(now), 3),
                    "expired": h.expired(now),
                }
                for k, h in self._holders.items()
            }
            return {
                **self._metrics,
                "active_runs": len(holders),
                "holders": holders,
                "gate_enabled": gate_enabled(self._env_getter()),
                "lease_s": self.lease_s,
                "dedup_window_s": self.dedup_window_s,
            }

    def active_holders(self) -> Dict[str, Holder]:
        with self._lock:
            return dict(self._holders)

    def reset(self) -> None:
        """测试用：清空全部状态与计数。"""
        with self._lock:
            self._holders.clear()
            self._fingerprints.clear()
            for k in self._metrics:
                self._metrics[k] = 0

    # -- 内部 -------------------------------------------------------------

    def _prune_fingerprints_locked(self, session_key: str, now: float) -> None:
        seen = self._fingerprints.get(session_key)
        if not seen:
            return
        stale = [
            fp for fp, (_tok, ts) in seen.items() if (now - ts) > self.dedup_window_s
        ]
        for fp in stale:
            del seen[fp]
        if len(seen) > self._max_fingerprints:
            ordered = sorted(seen.items(), key=lambda kv: kv[1][1])
            for fp, _v in ordered[: len(seen) - self._max_fingerprints]:
                del seen[fp]
        if not seen:
            self._fingerprints.pop(session_key, None)


_GATE: Optional[WakeGate] = None
_GATE_LOCK = threading.Lock()


def get_wake_gate() -> WakeGate:
    """进程级单例。"""
    global _GATE
    if _GATE is None:
        with _GATE_LOCK:
            if _GATE is None:
                _GATE = WakeGate()
    return _GATE


def reset_wake_gate() -> None:
    """测试用：重置单例状态（不换实例，避免调用方持有旧引用）。"""
    get_wake_gate().reset()


def wake_gate_snapshot() -> Dict[str, Any]:
    """便捷入口：/health 与排障用。"""
    return get_wake_gate().snapshot()
