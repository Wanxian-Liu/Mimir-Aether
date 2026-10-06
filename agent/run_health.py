"""run 级健康出声（B4 · 2026-10-06 · 任务书 行218「B4 观测」）。

## 病灶（盘上实证）
- 2026-10-06：当日 `empty_content` 3 次（15:03 / 15:22 / 17:53）+ `max_turns` 1 次（18:21 ·
  120 轮 · 841s · final_response 空）。**每一件都在 `agent/core_loop.py` 收尾表里明示过**
  （reason 串、ERROR 日志、故障正文），但**没有 run 级计数、没有阈值、没有出声**——
  于是「今天死了几次」只能靠外部巡视 grep 日志人工数（Hermes 侧 `今日静默死=N`）。
  观测缺口不是「不知道死」，是**不知道死了几次、何时越过阈值**。

## 本模块（观测层，不改判定）
- `record_run_exit(...)`：每个 run 收尾时落一行 `logs/run_health.jsonl`（append-only），
  并即时算**当日**计数（pure 函数 `daily_counts`）。
- `evaluate(counts, thresholds)`：pure 阈值判据 ⇒ 返回告警理由串（空 = 未越线）。
- 越线 ⇒ **出声**：`logger.error("[RUN_HEALTH_ALERT] ...")`（gateway.log 可 grep）
  + append `data/ops/run_health_alerts.jsonl`（告警台账）
  + 覆写 `data/ops/run_health_state.json`（当日计数快照 —— 外部巡视**读文件即可**，
    不必 grep 日志）。
- **幂等**：同一类告警**每自然日只出声一次**（state 里 `alerted[day][kind]=true`）；
  计数每 run 都更新，告警不重复刷屏。
- **失败开放**：本模块任何异常都吞掉并返回 dict（观测设施不得拖垮 run）——返回体里带 `error`。

## 判据源单一
退出原因 = `AgentResult.exit_reason`（core_loop 已解析，B3 半段兜底用同一变量）——
本模块**不另造 reason 分类**，只按既有串计数。

## 回滚
`MIMIR_RUN_HEALTH=0` ⇒ 不落盘、不告警（完全退化为现状）。

## 阈值（env，可调）
- `MIMIR_RUN_HEALTH_EMPTY_THRESHOLD`（默认 2）：当日 `empty_content` 计数
- `MIMIR_RUN_HEALTH_MAXTURNS_THRESHOLD`（默认 1）：当日 `max_turns` 计数
- `silent_death`（静默死族总数 = 上述两类 + `verify_exhausted` + `circuit_breaker`）**只进
  state/ledger 计数、不出声**——出声面严格等于任务书点名的两类，避免同一事实两声。
"""
from __future__ import annotations

import datetime as _dt
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

logger = logging.getLogger(__name__)

# 静默死族（计数用；判据串来自 core_loop 收尾表，不新增分类）
SILENT_DEATH_REASONS = ("empty_content", "max_turns", "verify_exhausted", "circuit_breaker")

# 逐类阈值映射：kind -> (env, default)。**出声只挂任务书点名的两类**（empty_content /
# max_turns）——`silent_death` 只进计数（state/ledger，供外部巡视读），不单独出声：
# 否则与逐类告警重复刷屏（受控差分实测：3 次 empty_content 会同时触发 empty_content 与
# silent_death 两条 ⇒ 同一事实两声响）。
_ALERT_KINDS = (
    ("empty_content", "MIMIR_RUN_HEALTH_EMPTY_THRESHOLD", 2),
    ("max_turns", "MIMIR_RUN_HEALTH_MAXTURNS_THRESHOLD", 1),
)


def health_enabled() -> bool:
    """总开关（回滚用）。"""
    return os.environ.get("MIMIR_RUN_HEALTH", "1").strip().lower() not in ("0", "false", "no", "off")


def _env_int(name: str, default: int) -> int:
    try:
        return max(0, int(os.environ.get(name, str(default)) or default))
    except Exception:
        return default


def thresholds() -> Dict[str, int]:
    return {kind: _env_int(env, default) for kind, env, default in _ALERT_KINDS}


def _home() -> Path:
    try:
        from mimir_constants import get_mimir_home  # type: ignore

        return Path(get_mimir_home())
    except Exception:
        env_home = os.environ.get("MIMIR_AETHER_HOME") or os.environ.get("MIMIR_HOME")
        return Path(env_home) if env_home else Path(os.path.expanduser("~/.mimiraether"))


def ledger_path() -> Path:
    return _home() / "logs" / "run_health.jsonl"


def alert_path() -> Path:
    return _home() / "data" / "ops" / "run_health_alerts.jsonl"


def state_path() -> Path:
    return _home() / "data" / "ops" / "run_health_state.json"


def today(now: Optional[_dt.datetime] = None) -> str:
    return (now or _dt.datetime.now()).strftime("%Y-%m-%d")


def daily_counts(lines: Iterable[str], day: str) -> Dict[str, int]:
    """pure：从 ledger 行算出 `day` 的计数。坏行跳过（不抛）。"""
    counts: Dict[str, int] = {"runs": 0, "silent_death": 0}
    for raw in lines:
        try:
            rec = json.loads(raw)
        except Exception:
            continue
        if not isinstance(rec, dict) or str(rec.get("date") or "") != day:
            continue
        counts["runs"] += 1
        reason = str(rec.get("exit_reason") or "")
        if reason in SILENT_DEATH_REASONS:
            counts["silent_death"] += 1
        if reason:
            counts[reason] = counts.get(reason, 0) + 1
    return counts


def evaluate(counts: Dict[str, int], thr: Optional[Dict[str, int]] = None) -> List[str]:
    """pure：越线告警理由（空列表 = 未越线）。`thr[kind] == 0` ⇒ 该条关闭。"""
    limits = thr if thr is not None else thresholds()
    out: List[str] = []
    for kind, _env, _default in _ALERT_KINDS:
        limit = int(limits.get(kind, 0) or 0)
        observed = int(counts.get(kind, 0) or 0)
        if limit > 0 and observed >= limit:
            out.append("%s=%d>=%d" % (kind, observed, limit))
    return out


def _read_lines(path: Path) -> List[str]:
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            return fh.readlines()
    except FileNotFoundError:
        return []
    except Exception:
        return []


def _read_state() -> Dict[str, Any]:
    try:
        with open(state_path(), "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _append_jsonl(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(payload, ensure_ascii=False) + "\n")


def record_run_exit(
    exit_reason: str,
    *,
    turns_used: int = 0,
    max_turns: int = 0,
    task_id: str = "",
    session_id: str = "",
    content_len: int = 0,
    now: Optional[_dt.datetime] = None,
) -> Dict[str, Any]:
    """一个 run 收尾时调用：落 ledger + 算当日计数 + 越线出声。

    **fail-open**：任何异常都吞掉并在返回体 `error` 里报出——绝不打断收尾路径。
    """
    result: Dict[str, Any] = {"enabled": False}
    if not health_enabled():
        return result
    try:
        stamp = now or _dt.datetime.now()
        day = today(stamp)
        rec = {
            "ts": stamp.isoformat(timespec="seconds"),
            "date": day,
            "exit_reason": str(exit_reason or ""),
            "turns_used": int(turns_used or 0),
            "max_turns": int(max_turns or 0),
            "task_id": str(task_id or ""),
            "session_id": str(session_id or ""),
            "content_len": int(content_len or 0),
        }
        _append_jsonl(ledger_path(), rec)

        counts = daily_counts(_read_lines(ledger_path()), day)
        thr = thresholds()
        reasons = evaluate(counts, thr)

        state = _read_state()
        alerted = state.get("alerted") if isinstance(state.get("alerted"), dict) else {}
        fired: List[str] = []
        for reason in reasons:
            kind = reason.split("=", 1)[0]
            day_flags = alerted.get(day) if isinstance(alerted.get(day), dict) else {}
            if day_flags.get(kind):
                continue
            day_flags[kind] = True
            alerted[day] = day_flags
            fired.append(reason)
            logger.error(
                "[RUN_HEALTH_ALERT] 当日 %s 计数越线：%s（阈值 %s）· runs=%d silent_death=%d",
                kind, reason, thr.get(kind), counts.get("runs", 0), counts.get("silent_death", 0),
            )
            _append_jsonl(alert_path(), {
                "ts": rec["ts"], "date": day, "kind": kind, "reason": reason,
                "counts": counts, "thresholds": thr,
            })

        state = {
            "updated_ts": rec["ts"],
            "date": day,
            "counts": counts,
            "thresholds": thr,
            "alerted": alerted,
        }
        sp = state_path()
        sp.parent.mkdir(parents=True, exist_ok=True)
        with open(sp, "w", encoding="utf-8") as fh:
            json.dump(state, fh, ensure_ascii=False, indent=2)

        result = {
            "enabled": True, "date": day, "counts": counts,
            "thresholds": thr, "fired": fired, "silent_death": counts.get("silent_death", 0),
        }
    except Exception as exc:  # pragma: no cover - 观测设施不得拖垮 run
        logger.warning("[RUN_HEALTH] 记录失败（已降级）：%s", exc)
        result = {"enabled": True, "error": "%s: %s" % (type(exc).__name__, exc)}
    return result
