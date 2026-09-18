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


def last_alert_at(job_id: str, path: Optional[Any] = None) -> Optional[str]:
    last: Optional[str] = None
    for rec in iter_alerts(path):
        if rec.get("job_id") == job_id and rec.get("ts"):
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
