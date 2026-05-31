"""WA-A06.1: search-first tool guard tests."""

from __future__ import annotations

from agent.search_first_guard import (
    block_tool_reason,
    cross_session_requires_search_first,
    exclude_user_message,
    session_search_satisfied_since_last_user,
    should_block_text_only_finish,
)


def test_cross_session_requires_explicit_phrase():
    assert cross_session_requires_search_first("查历史 IR-20260520")
    assert not cross_session_requires_search_first("继续离席清单")
    assert not cross_session_requires_search_first("世界模型是哲学问题")


def test_block_tool_until_session_search(monkeypatch):
    monkeypatch.setenv("MIMIR_SEARCH_FIRST_GUARD", "1")
    messages = [{"role": "user", "content": "我们之前讨论的 gateway 配置是什么"}]
    assert block_tool_reason("read_file", messages)
    assert block_tool_reason("session_search", messages) is None


def test_allow_other_tools_after_session_search(monkeypatch):
    monkeypatch.setenv("MIMIR_SEARCH_FIRST_GUARD", "1")
    messages = [
        {"role": "user", "content": "查历史 IR-99"},
        {
            "role": "assistant",
            "tool_calls": [{"function": {"name": "session_search"}}],
        },
        {"role": "tool", "tool_name": "session_search", "content": "hits: 2"},
    ]
    assert session_search_satisfied_since_last_user(messages)
    assert block_tool_reason("read_file", messages) is None


def test_text_only_finish_blocked(monkeypatch):
    monkeypatch.setenv("MIMIR_SEARCH_FIRST_GUARD", "1")
    messages = [{"role": "user", "content": "上次对话里 gateway 端口是多少"}]
    assert should_block_text_only_finish(
        messages, "应该是 18999。", has_tool_schemas=True
    )


def test_guard_off_no_block(monkeypatch):
    monkeypatch.setenv("MIMIR_SEARCH_FIRST_GUARD", "0")
    messages = [{"role": "user", "content": "查历史 IR-1"}]
    assert block_tool_reason("read_file", messages) is None
    assert not should_block_text_only_finish(
        messages, "answer", has_tool_schemas=True
    )


def test_exclude_shared_with_audit():
    assert exclude_user_message("继续离席") == "task_continuation"
