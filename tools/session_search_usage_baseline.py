"""IQ-EVO-29: 7-day session_search usage baseline from state.db."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict

from mimir_constants import get_mimir_home


def compute_session_search_baseline(*, days: int = 7, db_path: Path | None = None) -> Dict[str, Any]:
    """Return usage stats for session_search over the last ``days``."""
    from mimir_state import SessionDB

    path = db_path or (get_mimir_home() / "state.db")
    if not path.is_file():
        return {
            "ok": False,
            "error": f"state.db not found: {path}",
            "days": days,
        }

    cutoff = time.time() - days * 86400
    db = SessionDB(db_path=path)
    conn = db._conn

    total_sessions = int(
        conn.execute(
            "SELECT COUNT(*) FROM sessions WHERE started_at >= ?",
            (cutoff,),
        ).fetchone()[0]
    )

    sessions_with_search = int(
        conn.execute(
            """
            SELECT COUNT(DISTINCT s.id)
            FROM sessions s
            JOIN messages m ON m.session_id = s.id
            WHERE s.started_at >= ?
              AND (
                (m.role = 'tool' AND m.tool_name = 'session_search')
                OR (
                  m.role = 'assistant'
                  AND m.tool_calls IS NOT NULL
                  AND m.tool_calls LIKE '%"session_search"%'
                )
              )
            """,
            (cutoff,),
        ).fetchone()[0]
    )

    tool_row = conn.execute(
        """
        SELECT COUNT(*) FROM messages m
        JOIN sessions s ON s.id = m.session_id
        WHERE s.started_at >= ?
          AND m.role = 'tool' AND m.tool_name = 'session_search'
        """,
        (cutoff,),
    ).fetchone()[0]
    session_search_tool_messages = int(tool_row or 0)

    session_rate = (
        round(sessions_with_search / total_sessions, 4) if total_sessions else None
    )

    return {
        "ok": True,
        "days": days,
        "cutoff_unix": cutoff,
        "generated_at": time.time(),
        "state_db": str(path),
        "total_sessions": total_sessions,
        "sessions_with_session_search": sessions_with_search,
        "session_search_tool_messages": session_search_tool_messages,
        "session_search_session_rate": session_rate,
        "note": (
            "session_rate = sessions with ≥1 session_search / total sessions in window. "
            "Wave 6 target: increase vs prior baseline (document in bridge §4)."
        ),
    }


def default_output_path() -> Path:
    out_dir = get_mimir_home() / "data" / "ops"
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir / "session_search_baseline_7d.json"


def write_baseline_json(*, days: int = 7, db_path: Path | None = None) -> Dict[str, Any]:
    result = compute_session_search_baseline(days=days, db_path=db_path)
    out_path = default_output_path()
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return {**result, "output_path": str(out_path)}
