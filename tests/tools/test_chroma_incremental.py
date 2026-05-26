"""Chroma incremental upsert on sessions_search writes (IQ-EVO-11)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from tools.chroma_session_indexer import (
    IndexedMessage,
    chroma_incremental_enabled,
    reset_chroma_collection_cache,
    sync_message_to_chroma,
    sync_session_chroma_from_db,
)
from tools.session_search_indexer import index_transcript_message
from tools.session_search_tool import SessionSearchDB, get_session_search_backend


def test_default_session_search_backend_is_hybrid(monkeypatch):
    monkeypatch.delenv("SESSION_SEARCH_BACKEND", raising=False)
    assert get_session_search_backend() == "hybrid"


@patch("tools.chroma_session_indexer.chroma_available", return_value=True)
def test_chroma_incremental_enabled_by_default(_chroma):
    assert chroma_incremental_enabled() is True


@patch("tools.chroma_session_indexer.chroma_available", return_value=True)
def test_chroma_incremental_disabled_env(_chroma, monkeypatch):
    monkeypatch.setenv("MIMIR_CHROMA_INCREMENTAL", "0")
    assert chroma_incremental_enabled() is False


@patch("tools.chroma_session_indexer.chroma_incremental_enabled", return_value=True)
@patch("tools.chroma_session_indexer.upsert_indexed_messages", return_value=1)
def test_sync_message_to_chroma(mock_upsert, _enabled):
    msg = IndexedMessage(
        message_id=7,
        session_id="s1",
        role="user",
        content="hello",
        source="test",
        timestamp=1.0,
    )
    assert sync_message_to_chroma(msg) is True
    mock_upsert.assert_called_once_with([msg])


def test_index_transcript_message_triggers_chroma_sync(tmp_path):
    db_path = tmp_path / "sessions_search.db"
    db = SessionSearchDB(str(db_path))
    msg = {"role": "user", "content": "incremental chroma hook"}

    with patch("tools.chroma_session_indexer.sync_message_to_chroma") as mock_sync:
        assert index_transcript_message(
            "sid-chroma",
            msg,
            like_db=db,
            source="feishu",
            title="t",
        )
        mock_sync.assert_called_once()
        indexed = mock_sync.call_args[0][0]
        assert indexed.session_id == "sid-chroma"
        assert indexed.content == "incremental chroma hook"
        assert indexed.message_id == 1


@patch("tools.chroma_session_indexer.chroma_incremental_enabled", return_value=True)
@patch("tools.chroma_session_indexer.delete_session_chroma_documents")
@patch("tools.chroma_session_indexer.upsert_indexed_messages")
@patch("tools.chroma_session_indexer._get_incremental_collection")
def test_sync_session_chroma_from_db(
    mock_collection,
    mock_upsert,
    mock_delete,
    _enabled,
    tmp_path,
):
    reset_chroma_collection_cache()
    mock_collection.return_value = MagicMock()
    mock_upsert.return_value = 2
    db_path = tmp_path / "sessions_search.db"
    db = SessionSearchDB(str(db_path))
    db.add_session("s2", source="cli", title="demo")
    db.add_message("s2", "user", "one")
    db.add_message("s2", "assistant", "two")

    count = sync_session_chroma_from_db("s2", db_path)
    assert count == 2
    mock_delete.assert_called_once()
    assert mock_upsert.call_count >= 1
