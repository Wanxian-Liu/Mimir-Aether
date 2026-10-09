"""N12 (2026-09-18 · Mimir): event-triggered delivery-failure alerts.

Why an *event* trigger instead of a periodic scanner: the 12h ``n9-report``
poll was paused on 2026-09-18 (it re-sent the same report every cycle), which
left a blind window -- a real delivery outage would only be noticed by whoever
happened to read the job list. An outage *is* an event, so alert on the event.

Four rules, each one is a bug this family already produced:

1. **A broken target must not silence its own alarm.** The alert is sent to the
   HOME channel resolved through an explicit chat id, never through the target
   that just failed. (N8: bare ``deliver: "feishu"`` failed 3/3, silently.)
2. **The ledger is written whether or not the alert send worked**, so
   ``delivered=false`` stays observable instead of collapsing into "no alert".
   (N9: adapters *return* failures instead of raising them.)
3. **Rate limited per job** (default 30 min). A job failing every minute must
   not produce 1440 notifications; suppression is recorded, not hidden.
4. **Never raises.** An alarm path must never be able to break the cron loop.
   (N10: the same discipline.)
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterator, Mapping, Optional

from mimir_constants import get_mimir_home

LEDGER_RELATIVE = Path("data") / "ops" / "delivery_failure_alerts.jsonl"


# --- 预期（受控）投递失败 — 2026-10-07 第27单 ------------------------------
# 为什么写在 job spec（数据）而不是代码里：n8 投递双控 job 是**故意**投一个
# 不存在的 chat_id，它的失败就是预期结果。没有标记时该控制失败与真故障不可
# 区分：台账照记、告警器照推 HOME ⇒ 操作者每 12h 收到一条**形态与真事故完全
# 一样**的假警报（2026-10-07T03:59:57Z · job 71ea0213e413 实证）。
#
# job spec 接受两种写法：
#   expected_failures:        {"feishu:oc_0000…": "positive"}   # 目标 -> 控制标签
#   expected_failure_targets: ["feishu:oc_0000…"]               # 标签默认 "expected"
EXPECTED_FAILURES_KEY = "expected_failures"
EXPECTED_TARGETS_KEY = "expected_failure_targets"


def expected_failure_map(job: Optional[Mapping[str, Any]]) -> Dict[str, str]:
    """job spec 声明的「按设计就该失败」的投递目标。永不起抛。

    畸形 spec 退化为「没有任何预期」——这是安全方向：宁可警报吵，不可警报哑
    （与 rule 4 同族：告警路径不得因自身错误而静默）。
    """
    if not isinstance(job, Mapping):
        return {}
    out: Dict[str, str] = {}
    raw_map = job.get(EXPECTED_FAILURES_KEY)
    if isinstance(raw_map, Mapping):
        for target, label in raw_map.items():
            out[str(target)] = str(label or "expected")
    raw_list = job.get(EXPECTED_TARGETS_KEY)
    if isinstance(raw_list, (list, tuple)):
        for target in raw_list:
            out.setdefault(str(target), "expected")
    return out


def split_failures(failures, expected=None):
    """把投递失败按 spec 拆成 (expected, unexpected)，两者都是 dict。纯函数。"""
    expected = expected or {}
    exp: Dict[str, str] = {}
    unexp: Dict[str, str] = {}
    for target, reason in (failures or {}).items():
        key = str(target)
        (exp if key in expected else unexp)[key] = str(reason)
    return exp, unexp


def delivery_verdict(failures, expected=None):
    """O-11 (2026-10-09): one pure place turning raw delivery results into the
    verdict the ledger records.

    Returns a dict:
      ok         -- True when **no unexpected** target failed. A designed
                    (control-arm) failure must not make a job look broken;
      control    -- sorted list of control targets that failed == positive
                    evidence the control arm really ran this round;
      expected   -- {target: reason} for the control arm;
      unexpected -- {target: reason} for everything else (the real incident).
    """
    exp, unexp = split_failures(failures, expected)
    return {
        "ok": not unexp,
        "control": sorted(exp),
        "expected": exp,
        "unexpected": unexp,
    }


def default_cooldown_s() -> int:
    try:
        return int(os.getenv("MIMIR_DELIVERY_ALERT_COOLDOWN_S", "1800"))
    except (TypeError, ValueError):
        return 1800


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def alerts_path(path: Optional[Any] = None) -> Path:
    if path is not None:
        return Path(path)
    return Path(get_mimir_home()) / LEDGER_RELATIVE


def iter_alerts(path: Optional[Any] = None) -> Iterator[Dict[str, Any]]:
    """Yield ledger records, skipping malformed lines (never raise)."""
    p = alerts_path(path)
    try:
        raw = p.read_text(encoding="utf-8")
    except OSError:
        return
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(rec, dict):
            yield rec


def _parse_ts(value: Any) -> Optional[datetime]:
    try:
        parsed = datetime.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def last_alert_at(job_id: str, path: Optional[Any] = None, *, include_expected: bool = False) -> Optional[str]:
    """该 job 最近一次**真**告警时刻（2026-10-07 第27单：expected 行不计入）。

    受控控制行（expected=True）若计入冷却，n8 双控每 12h 的「预期失败」就会把
    同 job **真故障**的告警静音 30 min ⇒ 假警报的修法变成真警报的哑因。
    """
    last: Optional[str] = None
    for rec in iter_alerts(path):
        if rec.get("job_id") != job_id or not rec.get("ts"):
            continue
        if rec.get("expected") and not include_expected:
            continue
        last = str(rec["ts"])
    return last


def should_alert(
    job_id: str,
    now: Optional[datetime] = None,
    cooldown_s: Optional[int] = None,
    path: Optional[Any] = None,
) -> bool:
    """True when this job has not alerted within the cooldown window."""
    if cooldown_s is None:
        cooldown_s = default_cooldown_s()
    if cooldown_s <= 0:
        return True
    last = _parse_ts(last_alert_at(job_id, path))
    if last is None:
        return True
    return ((now or now_utc()) - last) >= timedelta(seconds=cooldown_s)


def format_job_failure_alert(job_id: str, job_name, reason: str) -> str:
    """S4 (2026-10-06): 「job 本身跑失败」的播报文案（区别于「投递失败」）。

    规矩 4「出错必须出声」：agent 型 job 可能以 empty_content / api_failure
    收尾且**没有正文**，旧形态连投递都不发生 ⇒ 台账记了 error 而无人被告知。
    本函数只负责文案，不发不收，便于单测。
    """
    return (
        f"⚠️ cron 任务**跑失败**：{job_name or '-'}（{job_id}）\n"
        f"失败原因：{reason or 'unknown'}\n"
        f"（本轮无正文产出；台账已记 last_status=error）"
    )


def format_alert(job_id: str, job_name: Optional[str], failures: Mapping[str, str]) -> str:
    """Human-readable alert. Pure function -> testable without a gateway."""
    lines = [
        "\u26a0 \u6295\u9012\u5931\u8d25\u544a\u8b66\uff08N12 \u4e8b\u4ef6\u89e6\u53d1\uff09",
        f"\u4efb\u52a1\uff1a{job_name or '-'}\uff08{job_id}\uff09",
        "\u5931\u8d25\u76ee\u6807\uff1a",
    ]
    for target, reason in (failures or {}).items():
        lines.append(f"- {target} \u2014 {reason}")
    lines.append(
        "\u672c\u6b21\u5df2\u8bb0\u5165 data/ops/delivery_failure_alerts.jsonl\uff1b"
        "\u672c\u544a\u8b66\u8d70 home \u9891\u9053\uff08\u663e\u5f0f chat_id\uff09\uff0c"
        "\u4e0d\u4f1a\u56e0\u5931\u8d25\u76ee\u6807\u800c\u9759\u9f13\u3002"
    )
    return "\n".join(lines)


def record_alert(
    job_id: str,
    job_name: Optional[str],
    failures: Mapping[str, str],
    delivered: bool,
    send_error: Optional[str] = None,
    expected: bool = False,
    control: Optional[str] = None,
    now: Optional[datetime] = None,
    path: Optional[Any] = None,
) -> Dict[str, Any]:
    """Append one alert record. Returns the record (also for tests)."""
    rec: Dict[str, Any] = {
        "ts": (now or now_utc()).isoformat(),
        "job_id": job_id,
        "job_name": job_name,
        "failed_targets": {str(k): str(v) for k, v in (failures or {}).items()},
        "delivered": bool(delivered),
        "send_error": send_error,
        # 2026-10-07 第27单：预期标记 —— 台账可查、日志可见、不推人。
        "expected": bool(expected),
        "control": str(control) if control else None,
    }
    p = alerts_path(path)
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except OSError:
        # Rule 4: never raise out of the alert path.
        pass
    return rec
