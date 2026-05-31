#!/usr/bin/env python3
"""Backfill mimir_state.SessionDB from gateway JSONL transcripts (IQ-IDX-01).

Gateway keeps JSONL under ``$MIMIR_AETHER_HOME/data/sessions/*.jsonl`` while
``state.db`` session rows were disabled in ``gateway/session.py`` (SQLite
create/end commented). This script is idempotent: ``INSERT OR IGNORE`` sessions,
skip messages when the session already has rows.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mimir_constants import get_mimir_home


def _parse_ts(raw: Any, session_id: str) -> float:
    if isinstance(raw, (int, float)):
        return float(raw)
    if isinstance(raw, str) and raw.strip():
        try:
            return datetime.fromisoformat(raw.replace("Z", "+00:00")).timestamp()
        except ValueError:
            pass
    # Fallback: session_id prefix YYYYMMDD_HHMMSS_*
    try:
        date_part, time_part, _ = session_id.split("_", 2)
        dt = datetime.strptime(f"{date_part}_{time_part}", "%Y%m%d_%H%M%S")
        return dt.timestamp()
    except ValueError:
        return time.time()


def _session_source(meta: Dict[str, Any], default: str = "jsonl_backfill") -> str:
    platform = meta.get("platform") or meta.get("source")
    if isinstance(platform, str) and platform.strip():
        return platform.strip().lower()
    return default


def _load_jsonl(path: Path) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def backfill_session(
    db: Any,
    session_id: str,
    messages: List[Dict[str, Any]],
    *,
    dry_run: bool,
) -> Dict[str, int]:
    stats = {"messages_appended": 0, "messages_skipped": 0, "sessions_created": 0}
    if not messages:
        return stats

    meta = messages[0] if messages[0].get("role") == "session_meta" else {}
    source = _session_source(meta if isinstance(meta, dict) else {})
    started_at = _parse_ts(
        (meta or {}).get("timestamp") if isinstance(meta, dict) else None,
        session_id,
    )

    existing = db.get_session(session_id)
    if existing:
        cur = db._conn.execute(
            "SELECT COUNT(*) FROM messages WHERE session_id = ?",
            (session_id,),
        ).fetchone()[0]
        if int(cur or 0) > 0:
            stats["messages_skipped"] = len(messages)
            return stats

    if dry_run:
        stats["sessions_created"] = 0 if existing else 1
        stats["messages_appended"] = len(messages)
        return stats

    if not existing:
        db.create_session(session_id, source=source, model=(meta or {}).get("model"))
        db._conn.execute(
            "UPDATE sessions SET started_at = ? WHERE id = ?",
            (started_at, session_id),
        )
        db._conn.commit()
        stats["sessions_created"] = 1
    else:
        db.ensure_session(session_id, source=source)

    for msg in messages:
        role = str(msg.get("role") or "user")
        if role == "session_meta":
            continue
        content = msg.get("content")
        if content is None:
            content = ""
        elif not isinstance(content, str):
            content = json.dumps(content, ensure_ascii=False)
        db.append_message(
            session_id,
            role=role,
            content=content,
            tool_name=msg.get("tool_name") or msg.get("name"),
            tool_calls=msg.get("tool_calls"),
            tool_call_id=msg.get("tool_call_id"),
            reasoning=msg.get("reasoning"),
        )
        stats["messages_appended"] += 1

    return stats


def run_backfill(
    *,
    sessions_dir: Path,
    db_path: Optional[Path],
    limit: Optional[int],
    dry_run: bool,
) -> Dict[str, Any]:
    from mimir_state import SessionDB

    sessions_dir = sessions_dir.expanduser()
    if not sessions_dir.is_dir():
        return {"ok": False, "error": f"sessions dir missing: {sessions_dir}"}

    db = SessionDB(db_path=db_path or (get_mimir_home() / "state.db"))
    files = sorted(sessions_dir.glob("*.jsonl"))
    if limit is not None:
        files = files[-limit:]

    totals = {
        "ok": True,
        "dry_run": dry_run,
        "sessions_dir": str(sessions_dir),
        "state_db": str(db.db_path),
        "files_seen": 0,
        "sessions_created": 0,
        "messages_appended": 0,
        "messages_skipped": 0,
    }

    for path in files:
        session_id = path.stem
        if not session_id or session_id.startswith("."):
            continue
        totals["files_seen"] += 1
        st = backfill_session(db, session_id, _load_jsonl(path), dry_run=dry_run)
        totals["sessions_created"] += st["sessions_created"]
        totals["messages_appended"] += st["messages_appended"]
        totals["messages_skipped"] += st["messages_skipped"]

    return totals


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--sessions-dir",
        type=Path,
        default=None,
        help="Default: $MIMIR_AETHER_HOME/data/sessions",
    )
    parser.add_argument("--db", type=Path, default=None)
    parser.add_argument("--limit", type=int, default=None, help="Only last N jsonl files")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    home = get_mimir_home()
    sessions_dir = args.sessions_dir or (home / "data" / "sessions")
    result = run_backfill(
        sessions_dir=sessions_dir,
        db_path=args.db,
        limit=args.limit,
        dry_run=args.dry_run,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
