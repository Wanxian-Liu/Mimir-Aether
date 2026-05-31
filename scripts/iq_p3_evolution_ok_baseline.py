#!/usr/bin/env python3
"""IQ-P3-00: snapshot post_analysis evolution ok% + production env flags (read-only)."""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent.synthetic_sessions import is_synthetic_session_id
from mimir_constants import get_mimir_home

_EVOLUTION_RE = re.compile(
    r"post_analysis evolution session_id=(\S+) applied=(\d+) ok=(\d+)"
)
_ENV_KEYS = (
    "MIMIR_AUTO_ANALYSIS",
    "MIMIR_AUTO_EVOLVE",
    "MIMIR_AUTO_TUNER",
    "MIMIR_FEEDBACK_COLLECTOR",
    "MIMIR_AUTO_1C_POLICY",
)


def _parse_env(home: Path) -> Dict[str, str]:
    env_path = home / ".env"
    out: Dict[str, str] = {}
    if not env_path.is_file():
        return out
    for line in env_path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip()
        if key in _ENV_KEYS:
            out[key] = val.strip().strip('"').strip("'")
    return out


def scan_agent_log(
    log_path: Path,
    *,
    days: float = 7.0,
    exclude_test_sessions: bool = True,
) -> Dict[str, Any]:
    if not log_path.is_file():
        return {
            "ok": False,
            "error": f"missing log: {log_path}",
            "lines": 0,
        }
    cutoff = time.time() - days * 86400.0
    lines_all: List[Dict[str, Any]] = []
    for raw in log_path.read_text(encoding="utf-8", errors="replace").splitlines():
        m = _EVOLUTION_RE.search(raw)
        if not m:
            continue
        session_id, applied_s, ok_s = m.group(1), int(m.group(2)), int(m.group(3))
        ts: Optional[float] = None
        try:
            from datetime import datetime

            ts_str = raw.split(",", 1)[0].strip()
            ts = datetime.strptime(ts_str, "%Y-%m-%d %H:%M:%S,%f").timestamp()
        except (ValueError, IndexError):
            pass
        if ts is not None and ts < cutoff:
            continue
        if exclude_test_sessions and is_synthetic_session_id(session_id):
            continue
        lines_all.append(
            {
                "session_id": session_id,
                "applied": applied_s,
                "ok": ok_s,
                "success": applied_s > 0 and ok_s > 0,
            }
        )

    total = len(lines_all)
    ok_lines = sum(1 for row in lines_all if row["success"])
    ok_pct = round(100.0 * ok_lines / total, 1) if total else None
    by_session: Dict[str, List[int]] = {}
    for row in lines_all:
        by_session.setdefault(row["session_id"], []).append(1 if row["success"] else 0)
    return {
        "ok": True,
        "log_path": str(log_path),
        "days": days,
        "exclude_test_sessions": exclude_test_sessions,
        "lines": total,
        "ok_lines": ok_lines,
        "ok_pct": ok_pct,
        "unique_sessions": len(by_session),
    }


def build_baseline(
    *,
    home: Optional[Path] = None,
    days: float = 7.0,
    write_path: Optional[Path] = None,
) -> Dict[str, Any]:
    home = home or get_mimir_home()
    log_path = home / "logs" / "agent.log"
    payload: Dict[str, Any] = {
        "ok": True,
        "generated_at": time.time(),
        "mimir_aether_home": str(home),
        "env": _parse_env(home),
        "evolution_7d": scan_agent_log(log_path, days=days, exclude_test_sessions=True),
        "evolution_7d_including_tests": scan_agent_log(
            log_path, days=days, exclude_test_sessions=False
        ),
    }
    if write_path:
        write_path.parent.mkdir(parents=True, exist_ok=True)
        write_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        payload["output_path"] = str(write_path)
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--home", type=Path, default=None)
    parser.add_argument("--days", type=float, default=7.0)
    parser.add_argument(
        "--write",
        type=Path,
        default=None,
        help="default: $MIMIR_AETHER_HOME/data/ops/iq-p3-baseline.json",
    )
    args = parser.parse_args()
    home = args.home or get_mimir_home()
    out = args.write or (home / "data" / "ops" / "iq-p3-baseline.json")
    payload = build_baseline(home=home, days=args.days, write_path=out)
    print(json.dumps(payload, indent=2))
    return 0 if payload.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
