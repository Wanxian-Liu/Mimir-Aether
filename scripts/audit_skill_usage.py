#!/usr/bin/env python3
"""7-day skill_view usage from agent logs → data/ops/skill-usage-7d.json."""

from __future__ import annotations

import json
import os
import re
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

_SKILL_VIEW_RE = re.compile(r"skill_view", re.IGNORECASE)
_ROUTE_RE = re.compile(r"skill-route nudge", re.IGNORECASE)
_NAME_RE = re.compile(r"mimiraether-[a-z0-9-]+", re.IGNORECASE)


def _home() -> Path:
    return Path(
        os.environ.get("MIMIR_AETHER_HOME")
        or os.environ.get("HERMES_HOME")
        or Path.home() / ".mimiraether"
    )


def scan_logs(days: int = 7) -> dict:
    home = _home()
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    skill_views = 0
    route_nudges = 0
    by_skill: Counter[str] = Counter()
    lines_scanned = 0
    logs_dir = home / "logs"
    if not logs_dir.is_dir():
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "window_days": days,
            "home": str(home),
            "lines_scanned": 0,
            "skill_view_7d": 0,
            "skill_route_nudge_7d": 0,
            "distinct_skills_7d": 0,
            "by_skill": {},
        }
    for path in sorted(logs_dir.glob("agent.log*")):
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for line in text.splitlines():
            m = re.match(r"(\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2})", line)
            if m:
                try:
                    ts = datetime.strptime(
                        m.group(1).replace("T", " "), "%Y-%m-%d %H:%M:%S"
                    ).replace(tzinfo=timezone.utc)
                    if ts < cutoff:
                        continue
                except ValueError:
                    pass
            lines_scanned += 1
            if _ROUTE_RE.search(line):
                route_nudges += 1
            if _SKILL_VIEW_RE.search(line):
                skill_views += 1
                for hit in _NAME_RE.findall(line):
                    by_skill[hit.lower()] += 1
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "window_days": days,
        "home": str(home),
        "lines_scanned": lines_scanned,
        "skill_view_7d": skill_views,
        "skill_route_nudge_7d": route_nudges,
        "distinct_skills_7d": len(by_skill),
        "by_skill": dict(by_skill.most_common(30)),
    }


def main() -> int:
    days = int(os.environ.get("SKILL_USAGE_DAYS", "7"))
    payload = scan_logs(days=days)
    out_dir = _home() / "data" / "ops"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "skill-usage-7d.json"
    out_path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(json.dumps({"ok": True, "path": str(out_path), **payload}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
