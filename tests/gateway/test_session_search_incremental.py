"""Gateway append_to_transcript dual-writes sessions_search.db (P1-M03)."""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture
def search_db_path(tmp_path, monkeypatch):
    db_path = tmp_path / "sessions_search.db"
    monkeypatch.delenv("MIMIR_SESSION_DB", raising=False)
    monkeypatch.setenv("OPENCLAW_SESSION_DB", str(db_path))
    monkeypatch.setenv("MIMIR_AETHER_HOME", str(tmp_path))
    monkeypatch.setenv("MIMIR_SESSION_SEARCH_INDEX", "1")
    return db_path


def test_append_indexes_with_mimir_session_db_env(tmp_path, monkeypatch):
    """IND-03: gateway indexing respects MIMIR_SESSION_DB."""
    db_path = tmp_path / "mimir_named.db"
    monkeypatch.delenv("OPENCLAW_SESSION_DB", raising=False)
    monkeypatch.setenv("MIMIR_SESSION_DB", str(db_path))
    monkeypatch.setenv("MIMIR_AETHER_HOME", str(tmp_path))
    monkeypatch.setenv("MIMIR_SESSION_SEARCH_INDEX", "1")

    from gateway.config import load_gateway_config
    from gateway.session import SessionStore

    sessions_dir = tmp_path / "sessions"
    store = SessionStore(sessions_dir, load_gateway_config())
    store.append_to_transcript("sid-mimir", {"role": "user", "content": "mimir env path"})

    conn = sqlite3.connect(str(db_path))
    try:
        count = conn.execute(
            "SELECT COUNT(*) FROM messages WHERE session_id = ?",
            ("sid-mimir",),
        ).fetchone()[0]
    finally:
        conn.close()
    assert count == 1


def test_append_to_transcript_indexes_sessions_search(tmp_path, search_db_path):
    from gateway.config import load_gateway_config
    from gateway.session import SessionStore

    sessions_dir = tmp_path / "sessions"
    store = SessionStore(sessions_dir, load_gateway_config())
    store.append_to_transcript("sid-1", {"role": "user", "content": "hello gateway"})

    conn = sqlite3.connect(str(search_db_path))
    try:
        count = conn.execute(
            "SELECT COUNT(*) FROM messages WHERE session_id = ? AND content LIKE ?",
            ("sid-1", "%hello gateway%"),
        ).fetchone()[0]
    finally:
        conn.close()
    assert count == 1


def test_append_skip_search_index_when_disabled(tmp_path, search_db_path, monkeypatch):
    monkeypatch.setenv("MIMIR_SESSION_SEARCH_INDEX", "0")

    from gateway.config import load_gateway_config
    from gateway.session import SessionStore

    sessions_dir = tmp_path / "sessions"
    store = SessionStore(sessions_dir, load_gateway_config())
    store.append_to_transcript("sid-2", {"role": "user", "content": "hidden"})

    if not search_db_path.exists():
        return
    conn = sqlite3.connect(str(search_db_path))
    try:
        count = conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
    finally:
        conn.close()
    assert count == 0


def test_rewrite_transcript_reindexes_sessions_search(tmp_path, search_db_path):
    from gateway.config import load_gateway_config
    from gateway.session import SessionStore

    sessions_dir = tmp_path / "sessions"
    store = SessionStore(sessions_dir, load_gateway_config())
    store.append_to_transcript("sid-3", {"role": "user", "content": "old text"})
    store.rewrite_transcript(
        "sid-3",
        [{"role": "user", "content": "new text only"}],
    )

    conn = sqlite3.connect(str(search_db_path))
    try:
        old = conn.execute(
            "SELECT COUNT(*) FROM messages WHERE session_id = ? AND content LIKE ?",
            ("sid-3", "%old text%"),
        ).fetchone()[0]
        new = conn.execute(
            "SELECT COUNT(*) FROM messages WHERE session_id = ? AND content LIKE ?",
            ("sid-3", "%new text only%"),
        ).fetchone()[0]
    finally:
        conn.close()
    assert old == 0
    assert new == 1
