"""Aggregate recent feedback events into tune inputs (IQ-EVO Wave 5).

仪器存活闸（2026-09-20 · IQ 批1③）
---------------------------------
本模块是 `data/feedback_events.jsonl` 的**读端**。历史缺口：文件缺失与「有文件但零事件」
都返回 `event_count = 0` ⇒ 消费端（auto_tuner / IQ 评分表）**无法区分**
「没有失败」与「量具坏了」。实证代价：该量具自 2026-08-16 13:44 停摆 35 天无人发现，
并在 IQ 第三次复评里被读成「能力下降」（#3 由 5.5 记到 4.5，全表最大跌幅）。

=> 现行约定（对齐 skill `mimiraether-agent-iq-measurement` 前置 1 / 铁律一）：

* 每次读数必须带 ``instrument_status``，取值 ``live`` / ``absent`` / ``stale``；
* ``absent`` / ``stale`` ⇒ 该维 **N/A + 分母剔除 + 单列「仪器债」**，绝不记 0；
* 非 live 读数在本进程内发一次 WARNING（同状态去重，防日志刷屏）。

开关语义：本读端只依赖**量具**开关（写端 ``MIMIR_FEEDBACK_COLLECTOR``），与执行器组
（``MIMIR_AUTO_ANALYSIS`` / ``MIMIR_AUTO_EVOLVE`` / ``MIMIR_AUTO_TUNER`` /
``MIMIR_AUTO_1C_POLICY``）无耦合 —— 见 `agent/feedback_collector.py` 的语义组单一真源。
"""

from __future__ import annotations

import json
import logging
import os
import time
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from mimir_constants import get_mimir_home

logger = logging.getLogger(__name__)

INSTRUMENT_LIVE = "live"
INSTRUMENT_ABSENT = "absent"
INSTRUMENT_STALE = "stale"

_STALE_ENV = "MIMIR_FEEDBACK_STALE_SECONDS"
_DEFAULT_STALE_SECONDS = 7 * 86400.0

_warned: set = set()


def _feedback_path(home: Optional[Path] = None) -> Path:
    root = Path(home) if home is not None else Path(get_mimir_home())
    return root / "data" / "feedback_events.jsonl"


def stale_threshold_seconds() -> float:
    """停更判据（默认 7 天，可用 env 覆盖；非法值回退默认并告警）。"""
    raw = os.environ.get(_STALE_ENV, "").strip()
    if not raw:
        return _DEFAULT_STALE_SECONDS
    try:
        val = float(raw)
    except ValueError:
        logger.warning(
            "[INSTRUMENT] %s 非法数值，回退默认值", _STALE_ENV
        )
        return _DEFAULT_STALE_SECONDS
    return val if val > 0 else _DEFAULT_STALE_SECONDS


def _warn_once(status: str, message: str) -> bool:
    """同状态每进程只告警一次；返回本次是否真发了。"""
    if status in _warned:
        return False
    _warned.add(status)
    logger.warning("[INSTRUMENT-DEBT] %s", message)
    return True


def reset_instrument_warnings() -> None:
    """测试助手：清空告警去重表。"""
    _warned.clear()


def instrument_status(
    *,
    path: Optional[Path] = None,
    now: Optional[float] = None,
) -> Dict[str, Any]:
    """判定量具存活：live / absent / stale（+ 读数元数据）。

    判据是**内容级**的（末条事件的 ts），不是「目录存在」——
    历史踩坑：把「父目录存在」当判据会静默产出假绿。
    """
    now = time.time() if now is None else float(now)
    stale_after = stale_threshold_seconds()
    p = Path(path) if path is not None else _feedback_path()
    info: Dict[str, Any] = {
        "instrument": "feedback_events",
        "path": str(p),
        "stale_after_s": stale_after,
        "now": now,
        "lines": 0,
        "last_ts": None,
        "last_event_type": None,
        "age_s": None,
        "reason": "",
        "status": INSTRUMENT_ABSENT,
    }
    if not p.is_file():
        info["reason"] = "file missing"
        _warn_once(
            INSTRUMENT_ABSENT,
            "feedback_events.jsonl 缺失（%s）=> 该维 N/A，不记 0" % p,
        )
        return info

    try:
        text = p.read_text(encoding="utf-8")
    except OSError as exc:
        info["reason"] = "unreadable: %r" % (exc,)
        _warn_once(INSTRUMENT_ABSENT, "feedback_events.jsonl 不可读 => 该维 N/A")
        return info

    last_ts: Optional[float] = None
    last_type: Optional[str] = None
    lines = 0
    for raw in text.splitlines():
        raw = raw.strip()
        if not raw:
            continue
        lines += 1
        try:
            row = json.loads(raw)
        except json.JSONDecodeError:
            continue
        ts = row.get("ts")
        if isinstance(ts, (int, float)):
            last_ts = float(ts)
            last_type = str(row.get("event_type") or "")
    info["lines"] = lines
    info["last_ts"] = last_ts
    info["last_event_type"] = last_type

    if last_ts is None:
        info["status"] = INSTRUMENT_ABSENT
        info["reason"] = "no timestamped event (empty or unparseable)"
        _warn_once(
            INSTRUMENT_ABSENT,
            "feedback_events.jsonl 无任何带 ts 的事件 => 该维 N/A，不记 0",
        )
        return info

    age = max(0.0, now - last_ts)
    info["age_s"] = age
    if age > stale_after:
        info["status"] = INSTRUMENT_STALE
        info["reason"] = "last event %.0fs ago > %.0fs" % (age, stale_after)
        _warn_once(
            INSTRUMENT_STALE,
            "feedback_events.jsonl 停更 %.1f 天（末条 %s）=> 该维 N/A，不记 0"
            % (age / 86400.0, last_type or "?"),
        )
        return info

    info["status"] = INSTRUMENT_LIVE
    return info


def _read_tail(path: Path, max_lines: int) -> List[str]:
    try:
        lines = path.read_text(encoding="utf-8").strip().splitlines()
    except OSError:
        return []
    return lines[-max(1, max_lines) :]


def summarize_recent_experience(*, max_lines: int = 200) -> Dict[str, Any]:
    """Read tail of feedback_events.jsonl, **with** instrument liveness.

    返回键（向后兼容旧 5 键 + 新增 3 键）：

    * ``event_count`` / ``tool_failure_count`` / ``pipeline_close_count`` /
      ``analysis_artifact_count`` / ``top_failed_tools``（旧契约，不动）
    * ``instrument``（dict：status/path/last_ts/age_s/reason 等）
    * ``instrument_status``（``live`` / ``absent`` / ``stale``）
    * ``scorable``（bool：True 才可把计数当能力证据；False = 记 N/A）
    """
    p = _feedback_path()
    info = instrument_status(path=p)
    counts: Dict[str, Any] = {
        "event_count": 0,
        "tool_failure_count": 0,
        "pipeline_close_count": 0,
        "analysis_artifact_count": 0,
        "top_failed_tools": [],
    }
    if info["status"] == INSTRUMENT_ABSENT and info["lines"] == 0 and not p.is_file():
        return _with_instrument(counts, info)

    tail = _read_tail(p, max_lines)
    types: Counter = Counter()
    tools: Counter = Counter()
    for line in tail:
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        et = str(row.get("event_type") or "")
        types[et] += 1
        if et == "tool_failure":
            payload = row.get("payload") or {}
            name = str(payload.get("tool_name") or "")
            if name:
                tools[name] += 1

    counts = {
        "event_count": sum(types.values()),
        "tool_failure_count": types.get("tool_failure", 0),
        "pipeline_close_count": types.get("pipeline_close", 0),
        "analysis_artifact_count": types.get("analysis_artifact", 0),
        "top_failed_tools": [t for t, _ in tools.most_common(5)],
    }
    return _with_instrument(counts, info)


def _with_instrument(counts: Dict[str, Any], info: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(counts)
    out["instrument"] = info
    out["instrument_status"] = info.get("status", INSTRUMENT_ABSENT)
    out["scorable"] = out["instrument_status"] == INSTRUMENT_LIVE
    if not out["scorable"]:
        # 消费端据此走 N/A 分支；此处显式给出口径，防再次「静默 0 假绿」。
        out["n_a_reason"] = "instrument_status=%s (%s)" % (
            out["instrument_status"],
            info.get("reason") or "",
        )
    return out
