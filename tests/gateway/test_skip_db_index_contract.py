"""skip_db contract: JSONL-only must ALSO skip the derived search index.

Audit 2026-09-12: ``gateway/session.py::append_to_transcript`` wrote to the search
index even when ``skip_db=True``, so callers asking for "only JSONL, skip the SQLite
write" still appended rows to ``data/sessions_search.db``. Bare-python3 Gate2 runs
deposited 800 fixture rows (sid-1 / sid / sid-rw, payload hello / x) into the
PRODUCTION index over 3.5 months.

Regression guards:
- skip_db=True  -> no session-DB write AND no search-index write;
- skip_db=False -> both happen (control, so the guard cannot be satisfied by
  disabling indexing altogether);
- rewrite_transcript -> search index rewritten once (it has no skip_db switch).
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from gateway.config import load_gateway_config
from gateway.session import SessionStore


def _store(tmp_path, db):
    return SessionStore(
        tmp_path / "sessions",
        load_gateway_config(),
        transcript_session_db=db,
    )


def test_skip_db_skips_session_db(tmp_path):
    db = MagicMock()
    store = _store(tmp_path, db)
    store.append_to_transcript("sid-1", {"role": "user", "content": "x"}, skip_db=True)
    db.append_message.assert_not_called()


def test_skip_db_also_skips_search_index(tmp_path):
    db = MagicMock()
    store = _store(tmp_path, db)
    with patch.object(store, "_append_to_sessions_search_index") as mock_index:
        store.append_to_transcript("sid-1", {"role": "user", "content": "x"}, skip_db=True)
    mock_index.assert_not_called()


def test_without_skip_db_indexes_search_index(tmp_path):
    db = MagicMock()
    store = _store(tmp_path, db)
    with patch.object(store, "_append_to_sessions_search_index") as mock_index:
        store.append_to_transcript("sid-2", {"role": "user", "content": "hello"})
    mock_index.assert_called_once()
    db.append_message.assert_called_once()


def test_rewrite_transcript_rewrites_search_index_once(tmp_path):
    db = MagicMock()
    store = _store(tmp_path, db)
    with patch.object(store, "_rewrite_sessions_search_index") as mock_rewrite:
        store.rewrite_transcript("sid-rw", [{"role": "user", "content": "one"}])
    mock_rewrite.assert_called_once()
