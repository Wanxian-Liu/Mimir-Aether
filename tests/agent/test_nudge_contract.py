"""SELF-12: Nudge contract tests.

Validates the search-first guard behavior:
- cross_session_requires_search_first() recognizes cross-session queries
- exclude_user_message() correctly filters false positives
- should_block_search_first_finish() blocks text-only cross-session responses
- block_tool_reason() blocks tools until session_search is called
"""

from __future__ import annotations

import os
from unittest import mock

from agent.search_first_guard import (
    cross_session_requires_search_first,
    exclude_user_message,
    guard_enabled,
    should_block_text_only_finish,
    block_tool_reason,
    last_user_text,
    session_search_satisfied_since_last_user,
)


# ========================================================================
# guard_enabled
# ========================================================================

class TestGuardEnabled:
    def test_enabled_by_default(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            assert guard_enabled() is True

    def test_disabled_via_env(self):
        with mock.patch.dict(os.environ, {"MIMIR_SEARCH_FIRST_GUARD": "0"}):
            assert guard_enabled() is False

    def test_disabled_via_false(self):
        with mock.patch.dict(os.environ, {"MIMIR_SEARCH_FIRST_GUARD": "false"}):
            assert guard_enabled() is False


# ========================================================================
# exclude_user_message — false positive filtering
# ========================================================================

class TestExcludeUserMessage:
    def test_empty_returns_excluded(self):
        assert exclude_user_message("") == "empty"
        assert exclude_user_message(None) == "empty"

    def test_user_paste_block(self):
        assert exclude_user_message("a" * 600).startswith("user_paste_block")

    def test_bridge_write_task(self):
        assert exclude_user_message("放入 Bridge") == "bridge_write_task"
        assert exclude_user_message("写入 Bridge §4") == "bridge_write_task"

    def test_fresh_session_continue(self):
        assert exclude_user_message("已经 new 了") == "fresh_session_continue"

    def test_same_session_recall(self):
        assert exclude_user_message("刚刚聊的那个") == "same_session_recall"

    def test_task_continuation(self):
        assert exclude_user_message("继续离席") == "task_continuation"
        assert exclude_user_message("继续入库") == "task_continuation"

    def test_user_provides_material(self):
        assert exclude_user_message("我给你发的资料") == "user_provides_material"
        assert exclude_user_message("如下是总结") == "user_provides_material"

    def test_in_scope_cross_session_query(self):
        assert exclude_user_message("还记得上次的任务么") == ""
        assert exclude_user_message("我们之前的决策是什么") == ""
        assert exclude_user_message("查一下历史记录") == ""


# ========================================================================
# cross_session_requires_search_first
# ========================================================================

class TestCrossSessionRequiresSearchFirst:
    def test_explicit_recall_chinese(self):
        assert cross_session_requires_search_first("还记得上次的任务么") is True

    def test_explicit_recall_decision(self):
        assert cross_session_requires_search_first("之前的决策是什么") is True

    def test_ir_reference(self):
        assert cross_session_requires_search_first("IR-20260520 的结论") is True

    def test_prior_session(self):
        assert cross_session_requires_search_first("prior session conclusions") is True

    def test_empty_false(self):
        assert cross_session_requires_search_first("") is False

    def test_chat_only_not_triggers(self):
        assert cross_session_requires_search_first("你好") is False
        assert cross_session_requires_search_first("继续") is False

    def test_bridge_task_excluded(self):
        assert cross_session_requires_search_first("放入 Bridge §4 一行") is False

    def test_same_session_excluded(self):
        assert cross_session_requires_search_first("刚刚聊的那个话题") is False


# ========================================================================
# block_tool_reason — tool dispatch guard
# ========================================================================

def _make_msgs(user: str, *tool_names: str) -> list:
    """Build a minimal message sequence."""
    msgs = [{"role": "user", "content": user}]
    for name in tool_names:
        msgs.append({
            "role": "assistant",
            "content": None,
            "tool_calls": [{"id": "t1", "type": "function",
                            "function": {"name": name, "arguments": "{}"}}],
        })
        msgs.append({"role": "tool", "tool_call_id": "t1", "content": "{}"})
    return msgs


class TestBlockToolReason:
    def test_blocks_non_search_tools_on_recall(self):
        msgs = _make_msgs("还记得上次的任务么")
        reason = block_tool_reason("read_file", msgs)
        assert reason is not None
        assert "session_search" in reason

    def test_allows_session_search(self):
        msgs = _make_msgs("还记得上次的任务么")
        reason = block_tool_reason("session_search", msgs)
        assert reason is None

    def test_does_not_block_on_normal_query(self):
        msgs = _make_msgs("你好")
        reason = block_tool_reason("read_file", msgs)
        assert reason is None

    def test_passes_after_search_satisfied(self):
        msgs = _make_msgs("还记得上次的任务么")
        msgs.append({
            "role": "assistant",
            "content": None,
            "tool_calls": [{"id": "srch", "type": "function",
                            "function": {"name": "session_search", "arguments": '{"query": "test"}'}}],
        })
        msgs.append({"role": "tool", "tool_call_id": "srch", "content": "{}"})
        assert session_search_satisfied_since_last_user(msgs)
        reason = block_tool_reason("read_file", msgs)
        assert reason is None

    def test_disabled_guard_passes_through(self):
        with mock.patch.dict(os.environ, {"MIMIR_SEARCH_FIRST_GUARD": "0"}):
            msgs = _make_msgs("还记得上次的任务么")
            reason = block_tool_reason("read_file", msgs)
            assert reason is None


# ========================================================================
# should_block_text_only_finish — post-hoc guard
# ========================================================================

class TestShouldBlockTextOnlyFinish:
    def test_blocks_text_only_on_recall(self):
        msgs = [{"role": "user", "content": "还记得上次的任务么"}]
        assert should_block_text_only_finish(
            msgs, "我觉得上次的任务是X",
            has_tool_schemas=True,
        ) is True

    def test_allows_text_with_schemas_disabled(self):
        msgs = [{"role": "user", "content": "还记得上次的任务么"}]
        assert should_block_text_only_finish(
            msgs, "我觉得上次的任务是X",
            has_tool_schemas=False,
        ) is False

    def test_allows_after_search_satisfied(self):
        msgs = [{"role": "user", "content": "还记得上次的任务么"}]
        msgs.append({
            "role": "assistant",
            "content": None,
            "tool_calls": [{"id": "srch", "type": "function",
                            "function": {"name": "session_search", "arguments": "{}"}}],
        })
        msgs.append({"role": "tool", "tool_call_id": "srch", "content": "{}"})
        assert should_block_text_only_finish(
            msgs, "上次的任务是X",
            has_tool_schemas=True,
        ) is False

    def test_does_not_block_normal_queries(self):
        msgs = [{"role": "user", "content": "你好"}]
        assert should_block_text_only_finish(
            msgs, "你好！",
            has_tool_schemas=True,
        ) is False

    def test_does_not_block_after_preemptive_search(self):
        msgs = [
            {"role": "user", "content": "还记得上次的任务么"},
            {
                "role": "user",
                "content": "[SEARCH-FIRST-RESULTS] Queried sessions.\nmatches: 2",
            },
        ]
        assert session_search_satisfied_since_last_user(msgs) is True
        assert should_block_text_only_finish(
            msgs, "上次的任务是 X",
            has_tool_schemas=True,
        ) is False


# ========================================================================
# last_user_text — skip injected nudges
# ========================================================================

class TestLastUserText:
    def test_skips_preemptive_and_guard_messages(self):
        msgs = [
            {"role": "user", "content": "还记得上次的任务么"},
            {"role": "user", "content": "[SEARCH-FIRST-RESULTS] Queried sessions."},
            {"role": "user", "content": "[search-first-guard] must call session_search"},
        ]
        assert last_user_text(msgs) == "还记得上次的任务么"

    def test_preemptive_satisfies_without_tool_call(self):
        msgs = [
            {"role": "user", "content": "还记得上次的任务么"},
            {"role": "user", "content": "[SEARCH-FIRST-RESULTS] Queried sessions."},
        ]
        assert block_tool_reason("read_file", msgs) is None
