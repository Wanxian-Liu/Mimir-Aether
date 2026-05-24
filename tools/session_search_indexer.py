"""Backfill session_search.db and optional fts5_search.db from gateway JSONL transcripts."""

from __future__ import annotations

import json
import logging
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterator, Optional, Tuple

logger = logging.getLogger(__name__)

_SKIP_ROLES = frozenset({"session_meta"})


def _parse_timestamp(raw: Any) -> float:
    if raw is None:
        return datetime.now().timestamp()
    if isinstance(raw, (int, float)):
        return float(raw)
    if isinstance(raw, str):
        try:
            return datetime.fromisoformat(raw.replace("Z", "+00:00")).timestamp()
        except ValueError:
            pass
    return datetime.now().timestamp()


def extract_searchable_message(record: Dict[str, Any]) -> Optional[Tuple[str, str, Optional[str], float]]:
    """Return (role, content, tool_name, timestamp) or None if not indexable."""
    role = record.get("role")
    if not role or role in _SKIP_ROLES:
        return None
    content = record.get("content") or record.get("text") or ""
    if not isinstance(content, str):
        return None
    content = content.strip()
    if not content:
        tool_calls = record.get("tool_calls")
        if isinstance(tool_calls, list) and tool_calls:
            names = []
            for tc in tool_calls:
                if isinstance(tc, dict):
                    name = tc.get("name") or (tc.get("function") or {}).get("name")
                    if name:
                        names.append(str(name))
            if names:
                content = f"[Called: {', '.join(names)}]"
        if not content:
            return None
    tool_name = record.get("tool_name") or record.get("name")
    if tool_name is not None:
        tool_name = str(tool_name)
    return str(role), content, tool_name, _parse_timestamp(record.get("timestamp"))


def load_sessions_index(sessions_dir: Path) -> Dict[str, Dict[str, Any]]:
    """Load gateway sessions.json mapping session_id -> metadata."""
    index_path = sessions_dir / "sessions.json"
    if not index_path.exists():
        return {}
    try:
        data = json.loads(index_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Failed to read %s: %s", index_path, exc)
        return {}
    if not isinstance(data, dict):
        return {}
    by_id: Dict[str, Dict[str, Any]] = {}
    for entry in data.values():
        if not isinstance(entry, dict):
            continue
        sid = entry.get("session_id")
        if sid:
            by_id[str(sid)] = entry
    return by_id


def iter_transcript_messages(path: Path) -> Iterator[Tuple[int, Dict[str, Any]]]:
    with path.open(encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                yield line_no, json.loads(line)
            except json.JSONDecodeError:
                logger.debug("Skip invalid JSON in %s:%s", path, line_no)


@dataclass
class BackfillStats:
    sessions: int = 0
    messages: int = 0
    skipped_files: int = 0
    fts_messages: int = 0


def clear_like_db(db_path: Path) -> None:
    conn = sqlite3.connect(str(db_path))
    try:
        conn.execute("DELETE FROM messages")
        conn.execute("DELETE FROM sessions")
        conn.commit()
    finally:
        conn.close()


def backfill_sessions(
    sessions_dir: Path,
    *,
    like_db_path: Path,
    fts_db_path: Optional[Path] = None,
    fresh: bool = False,
) -> BackfillStats:
    """Index all *.jsonl transcripts under sessions_dir into search DB(s)."""
    from tools.session_search_tool import SessionSearchDB

    stats = BackfillStats()
    if not sessions_dir.is_dir():
        logger.warning("Sessions dir missing: %s", sessions_dir)
        return stats

    like_db_path.parent.mkdir(parents=True, exist_ok=True)
    if fresh and like_db_path.exists():
        clear_like_db(like_db_path)

    like_db = SessionSearchDB(str(like_db_path))

    fts_engine = None
    if fts_db_path is not None:
        if fresh and fts_db_path.exists():
            fts_db_path.unlink(missing_ok=True)
        from tools.fts5_search.engine import FTS5SearchEngine

        fts_engine = FTS5SearchEngine(str(fts_db_path))

    index = load_sessions_index(sessions_dir)

    for path in sorted(sessions_dir.glob("*.jsonl")):
        session_id = path.stem
        meta = index.get(session_id, {})
        source = str(meta.get("platform") or meta.get("source") or "unknown")
        title = str(meta.get("display_name") or meta.get("title") or session_id)
        msg_count = 0

        like_db.add_session(session_id, source=source, title=title)

        for _line_no, record in iter_transcript_messages(path):
            parsed = extract_searchable_message(record)
            if parsed is None:
                continue
            role, content, tool_name, _ts = parsed
            like_db.add_message(session_id, role, content, tool_name=tool_name)
            msg_count += 1
            if fts_engine is not None:
                fts_engine.index_message(
                    session_id,
                    role,
                    content,
                    metadata={"source": source, "title": title},
                )
                stats.fts_messages += 1

        if msg_count:
            stats.sessions += 1
            stats.messages += msg_count
        else:
            stats.skipped_files += 1

    if fts_engine is not None:
        fts_engine.close()

    return stats


def index_transcript_message(
    session_id: str,
    message: Dict[str, Any],
    *,
    like_db: Any,
    source: str = "unknown",
    title: str = "",
    ensure_session: bool = True,
) -> bool:
    """Append one JSONL transcript row to sessions_search.db. Returns True if indexed."""
    parsed = extract_searchable_message(message)
    if parsed is None:
        return False
    role, content, tool_name, _ts = parsed
    if ensure_session:
        like_db.add_session(session_id, source=source, title=title)
    like_db.add_message(session_id, role, content, tool_name=tool_name)
    return True


def reindex_session_transcript(
    session_id: str,
    messages: list,
    *,
    like_db: Any,
    source: str = "unknown",
    title: str = "",
) -> int:
    """Replace search index rows for a session (e.g. after rewrite_transcript)."""
    clear = getattr(like_db, "clear_session_messages", None)
    if callable(clear):
        clear(session_id)
    like_db.add_session(session_id, source=source, title=title)
    count = 0
    for message in messages:
        if index_transcript_message(
            session_id,
            message,
            like_db=like_db,
            source=source,
            title=title,
            ensure_session=False,
        ):
            count += 1
    return count
