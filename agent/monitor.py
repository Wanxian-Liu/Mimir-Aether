"""E-006 D6-0b — agent tool error-rate monitoring and health snapshot."""

from __future__ import annotations

import json
import os
import threading
import time
from collections import deque
from pathlib import Path
from typing import Any, Deque, Dict, List, Optional

DEFAULT_ERROR_RATE_THRESHOLD = 0.10
CHECK_EVERY_N_CALLS = 10
WINDOW_SECONDS = 300.0

# QC7(1) 最小样本量：n < MIN_SAMPLES 时不得判 degraded（四方 C 组审计 2026-09-16）。
# 统计依据见 notes/2026-09-16-QC7-告警判据统计表.md：阈 0.10、真失败率 q=0.05 时
# 假警率 n=7 -> 30.17% / n=20 -> 7.55% / n=30 -> 6.08% / n=40 -> 4.80%，取 30。
DEFAULT_MIN_SAMPLES = 30
# 紧急底线：绝对失败数达此值则忽略样本闸（防真事故被小样本闸闷掉）。
DEFAULT_MIN_ERRORS_EMERGENCY = 5

# QC7(2) 来源标签：agent_bug 不进系统告警池；system_failure / unspecified 进。
SOURCE_AGENT_BUG = "agent_bug"
SOURCE_SYSTEM_FAILURE = "system_failure"
SOURCE_UNSPECIFIED = "unspecified"


def get_monitor_error_rate_threshold() -> float:
    """Tool error-rate cap for degraded status (OBS-B1-02 · override via env)."""
    raw = os.environ.get("MIMIR_MONITOR_ERROR_RATE_THRESHOLD", "").strip()
    if raw:
        try:
            value = float(raw)
            if 0.0 < value <= 1.0:
                return value
        except ValueError:
            pass
    return DEFAULT_ERROR_RATE_THRESHOLD


def get_monitor_min_samples() -> int:
    """QC7(1) 最小样本量（env 覆盖；非法值回退默认，不抛）。"""
    raw = os.environ.get("MIMIR_MONITOR_MIN_SAMPLES", "").strip()
    if raw:
        try:
            value = int(raw)
            if value > 0:
                return value
        except ValueError:
            pass
    return DEFAULT_MIN_SAMPLES


def get_monitor_min_errors_emergency() -> int:
    """QC7(1) 紧急底线：绝对失败数达此值即报警，忽略样本量。"""
    raw = os.environ.get("MIMIR_MONITOR_MIN_ERRORS_EMERGENCY", "").strip()
    if raw:
        try:
            value = int(raw)
            if value > 0:
                return value
        except ValueError:
            pass
    return DEFAULT_MIN_ERRORS_EMERGENCY


# 启发式分类（是启发式，不是判决；错分只改归因，不改「是否记录」）。
_AGENT_BUG_SIGNS = (
    "KeyError", "NameError", "SyntaxError", "IndentationError",
    "AttributeError", "IndexError", "UnboundLocalError", "ZeroDivisionError",
    "missing position", "unexpected keyword", "positional argument",
)
_SYSTEM_SIGNS = (
    "Connection refused", "Connection reset", "Temporary failure",
    "Resource temporarily unavailable", "No space left", "ENOMEM",
    "Cannot allocate memory", "Broken pipe", "gateway unavailable",
)


def classify_error_source(tool_name: str, error_message: str) -> str:
    """按错误签名把一次失败归到 agent_bug / system_failure / unspecified。"""
    msg = error_message or ""
    for sign in _SYSTEM_SIGNS:
        if sign in msg:
            return SOURCE_SYSTEM_FAILURE
    for sign in _AGENT_BUG_SIGNS:
        if sign in msg:
            return SOURCE_AGENT_BUG
    return SOURCE_UNSPECIFIED


def get_monitor_window_seconds() -> float:
    """Sliding window for error rate and latency percentiles (seconds)."""
    raw = os.environ.get("MIMIR_MONITOR_WINDOW_SECONDS", "").strip()
    if raw:
        try:
            value = float(raw)
            if value > 0:
                return value
        except ValueError:
            pass
    return WINDOW_SECONDS

_lock = threading.RLock()
_recent: Deque[Dict[str, Any]] = deque(maxlen=1000)
_total_calls = 0
_alerts_path: Optional[Path] = None


def _alerts_file() -> Path:
    global _alerts_path
    if _alerts_path is None:
        from mimir_constants import get_mimir_home

        path = Path(get_mimir_home()) / "data" / "monitor_alerts.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        _alerts_path = path
    return _alerts_path


def record_tool_outcome(
    tool_name: str,
    *,
    success: bool,
    duration_ms: float = 0.0,
    error_message: str = "",
    session_id: str = "",
    source_tag: str = SOURCE_UNSPECIFIED,
) -> None:
    """Track one tool call outcome; may emit monitor_alerts.json.

    source_tag（QC7(2)）：本次失败归谁 —— agent_bug / system_failure / unspecified。
    只有 agent_bug 被排除出系统告警池；其余（含默认）照旧计入（保持历史行为）。
    """
    global _total_calls
    entry = {
        "ts": time.time(),
        "tool_name": tool_name,
        "success": success,
        "duration_ms": duration_ms,
        "error_message": error_message or "",
        "session_id": session_id,
        "source_tag": source_tag or SOURCE_UNSPECIFIED,
    }
    with _lock:
        _recent.append(entry)
        _total_calls += 1
        if _total_calls % CHECK_EVERY_N_CALLS == 0:
            _maybe_write_alert_locked()
    if not success:
        try:
            from agent.feedback_collector import record_tool_outcome_feedback

            record_tool_outcome_feedback(
                tool_name,
                success=False,
                duration_ms=duration_ms,
                error_message=error_message,
                session_id=session_id,
            )
        except Exception:
            pass


def get_agent_error_rate(
    window_seconds: Optional[float] = None,
) -> float:
    if window_seconds is None:
        window_seconds = get_monitor_window_seconds()
    """Error rate in [0, 1] over the sliding window."""
    cutoff = time.time() - window_seconds
    with _lock:
        window = [e for e in _recent if e["ts"] >= cutoff]
    if not window:
        return 0.0
    errors = sum(1 for e in window if not e["success"])
    return errors / len(window)


def get_system_pool(window_seconds: Optional[float] = None) -> List[Dict[str, Any]]:
    """系统告警池 = 窗口内排除 source_tag=agent_bug 的调用（QC7(2) 口径分段）。"""
    if window_seconds is None:
        window_seconds = get_monitor_window_seconds()
    cutoff = time.time() - window_seconds
    with _lock:
        return [
            e for e in _recent
            if e["ts"] >= cutoff and e.get("source_tag") != SOURCE_AGENT_BUG
        ]


def get_agent_error_rate_detail(
    window_seconds: Optional[float] = None,
    threshold: Optional[float] = None,
    min_samples: Optional[int] = None,
) -> Dict[str, Any]:
    """QC7 口径全量：系统池 rate/calls/errors + 是否报警 + 原因 + 来源分布。

    status: degraded（越阈且样本够或达紧急底线）/ insufficient_samples（越阈但样本不足）/
    ok（未越阈）。insufficient_samples 是显式第三态，供调用方区分「真坏」与「数据不够」。
    """
    if threshold is None:
        threshold = get_monitor_error_rate_threshold()
    if min_samples is None:
        min_samples = get_monitor_min_samples()
    emergency = get_monitor_min_errors_emergency()
    pool = get_system_pool(window_seconds)
    calls = len(pool)
    errors = sum(1 for e in pool if not e["success"])
    rate = (errors / calls) if calls else 0.0
    by_source: Dict[str, Dict[str, int]] = {}
    for e in pool:
        tag = e.get("source_tag") or SOURCE_UNSPECIFIED
        slot = by_source.setdefault(tag, {"calls": 0, "errors": 0})
        slot["calls"] += 1
        if not e["success"]:
            slot["errors"] += 1
    # 被排除出系统池的部分（agent_bug）单独计数 —— 否则「排除」本身不可审计。
    cutoff = time.time() - (window_seconds if window_seconds is not None else get_monitor_window_seconds())
    with _lock:
        excluded = [
            e for e in _recent
            if e["ts"] >= cutoff and e.get("source_tag") == SOURCE_AGENT_BUG
        ]
    excluded_agent_bug = {
        "calls": len(excluded),
        "errors": sum(1 for e in excluded if not e["success"]),
    }
    over = rate > threshold
    alarm = bool(over and (calls >= min_samples or errors >= emergency))
    if alarm:
        status, reason = "degraded", "rate_above_threshold"
    elif over:
        status, reason = "insufficient_samples", "insufficient_samples"
    else:
        status, reason = "ok", "ok"
    return {
        "rate": rate,
        "calls": calls,
        "errors": errors,
        "threshold": threshold,
        "min_samples": min_samples,
        "min_errors_emergency": emergency,
        "alarm": alarm,
        "status": status,
        "reason": reason,
        "by_source": by_source,
        "excluded_agent_bug": excluded_agent_bug,
    }


def get_agent_health_status(
    threshold: Optional[float] = None,
) -> str:
    d = get_agent_error_rate_detail(threshold=threshold)
    if d["alarm"]:
        return "degraded"
    if d["rate"] > d["threshold"]:
        return "insufficient_samples"
    return "ok"


def _percentile(values: List[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = int(round((pct / 100.0) * (len(ordered) - 1)))
    idx = max(0, min(idx, len(ordered) - 1))
    return ordered[idx]


def get_tool_duration_percentiles(
    window_seconds: Optional[float] = None,
) -> Dict[str, float]:
    if window_seconds is None:
        window_seconds = get_monitor_window_seconds()
    """P50/P95/P99 tool call latency (ms) over the sliding window."""
    cutoff = time.time() - window_seconds
    with _lock:
        durs = [
            float(e["duration_ms"])
            for e in _recent
            if e["ts"] >= cutoff and float(e.get("duration_ms") or 0) > 0
        ]
    return {
        "p50_ms": _percentile(durs, 50),
        "p95_ms": _percentile(durs, 95),
        "p99_ms": _percentile(durs, 99),
    }


def snapshot_for_health() -> Dict[str, Any]:
    rate = get_agent_error_rate()
    detail = get_agent_error_rate_detail()
    pct = get_tool_duration_percentiles()
    payload = {
        "agent": get_agent_health_status(),
        "agent_error_rate": round(rate, 4),
        "agent_error_calls": detail["calls"],
        "agent_error_reason": detail["reason"],
        "agent_error_min_samples": detail["min_samples"],
        "agent_error_by_source": detail["by_source"],
        "agent_tool_p50_ms": round(pct["p50_ms"], 1),
        "agent_tool_p95_ms": round(pct["p95_ms"], 1),
        "agent_tool_p99_ms": round(pct["p99_ms"], 1),
    }
    # U16/RS1-③（2026-09-13）：wake_gate 计数器此前**只在进程内存**，且
    # wake_gate_snapshot() 全仓**零消费者** ⇒ 无法区分「闸跑了并放行」与
    # 「闸根本没跑」。挂到 /health（api_server._handle_health 已 update 本 dict）；
    # 失败静默降级——观测不得拖垮健康端点。
    try:
        from gateway.wake_gate import wake_gate_snapshot

        payload["wake_gate"] = wake_gate_snapshot()
    except Exception:  # pragma: no cover - 可选增强
        pass
    return payload


def _maybe_write_alert_locked() -> None:
    """QC7：只在**系统池**上判、且受样本闸约束；payload 带样本量与来源分布。"""
    detail = get_agent_error_rate_detail()
    rate = detail["rate"]
    threshold = detail["threshold"]
    if not detail["alarm"]:
        return
    pool = get_system_pool()
    recent_errors = [e for e in pool[-20:] if not e["success"]]
    payload = {
        "timestamp": time.time(),
        "agent_error_rate": round(rate, 4),
        "threshold": threshold,
        "sample_size": detail["calls"],
        "min_samples": detail["min_samples"],
        "min_errors_emergency": detail["min_errors_emergency"],
        "pool": "excludes source_tag=agent_bug",
        "by_source": detail["by_source"],
        "recent_errors": recent_errors,
    }
    path = _alerts_file()
    try:
        existing: List[Dict[str, Any]] = []
        if path.exists():
            existing = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(existing, list):
                existing = [existing]
        existing.append(payload)
        path.write_text(json.dumps(existing[-50:], ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError:
        pass


def reset_monitor_state() -> None:
    """Test helper."""
    global _total_calls, _alerts_path
    with _lock:
        _recent.clear()
        _total_calls = 0
        _alerts_path = None
