"""Tests for session_search_indexer."""

from tools.session_search_indexer import extract_searchable_message


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
