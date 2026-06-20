"""WA-A06.1: search-first tool guard tests. +3 ENG-WF-13."""

from __future__ import annotations

from agent.search_first_guard import (
    _is_injected_user_message,
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


# === ENG-WF-13: +3 tests covering failure branches ===


def test_exclude_user_paste_block():
    """Long text + box-drawing chars → excluded as user_paste_block."""
    long_paste = "┌────┐\n│ hi │\n└────┘" * 20  # >500 chars with box drawing
    assert exclude_user_message(long_paste) == "user_paste_block"


def test_exclude_same_session_recall():
    """刚聊/刚才聊 → excluded as same_session_recall."""
    assert exclude_user_message("刚才聊的继续") == "same_session_recall"
    assert exclude_user_message("刚才说那件事") == "same_session_recall"


def test_block_text_only_empty_content(monkeypatch):
    """Empty assistant content still blocked under cross-session task."""
    monkeypatch.setenv("MIMIR_SEARCH_FIRST_GUARD", "1")
    messages = [{"role": "user", "content": "我们之前聊过 gateway 吗"}]
    assert should_block_text_only_finish(
        messages, "", has_tool_schemas=True
    )
    assert should_block_text_only_finish(
        messages, "   ", has_tool_schemas=True
    )


def test_satisfied_by_search_first_marker(monkeypatch):
    """SEARCH-FIRST-RESULTS marker satisfies 'satisfied since last user'."""
    monkeypatch.setenv("MIMIR_SEARCH_FIRST_GUARD", "1")
    messages = [
        {"role": "user", "content": "查历史 IR-99"},
        {"role": "user", "content": "[SEARCH-FIRST-RESULTS] Queried sessions."},
    ]
    assert session_search_satisfied_since_last_user(messages)
    assert block_tool_reason("read_file", messages) is None


def test_injected_message_prefixes():
    """All injected prefixes are recognized."""
    assert _is_injected_user_message("[search-first-guard] call session_search")
    assert _is_injected_user_message("[SEARCH-FIRST-RESULTS] found 2 results")
    assert _is_injected_user_message("[intent-action-guard] use tools")
    assert not _is_injected_user_message("正常的用户消息")

