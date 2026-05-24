"""Tests for session_search_indexer."""

from tools.session_search_indexer import extract_searchable_message, reindex_session_transcript
from tools.session_search_tool import SessionSearchDB


def test_extract_user_message():
    parsed = extract_searchable_message(
        {"role": "user", "content": "hello", "timestamp": "2026-05-12T04:01:14"}
    )
    assert parsed is not None
    role, content, tool_name, _ts = parsed
    assert role == "user"
    assert content == "hello"
    assert tool_name is None


def test_skip_session_meta():
    assert extract_searchable_message({"role": "session_meta", "platform": "feishu"}) is None


def test_tool_calls_fallback_content():
    parsed = extract_searchable_message(
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [{"name": "read_file"}],
        }
    )
    assert parsed is not None
    assert "read_file" in parsed[1]


def test_reindex_session_transcript_replaces_messages(tmp_path):
    db_path = tmp_path / "search.db"
    db = SessionSearchDB(str(db_path))
    db.add_session("s1", source="test", title="t")
    db.add_message("s1", "user", "old")
    n = reindex_session_transcript(
        "s1",
        [{"role": "user", "content": "new"}],
        like_db=db,
        source="test",
        title="t",
    )
    assert n == 1
    results = db.search("new", session_limit=1)
    assert results and results[0]["messages"]
    assert "new" in results[0]["messages"][0]["content"]
    assert not db.search("old", session_limit=1)
