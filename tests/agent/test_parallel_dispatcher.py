"""Tests for parallel tool dispatcher (MW-02).

Uses asyncio.run() for async dispatch tests (no pytest-asyncio plugin).
"""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import MagicMock, patch

import pytest

from agent.parallel_dispatcher import (
    dispatch_all,
    is_read_only,
    parallel_tools_enabled,
)


class TestIsReadOnly:
    def test_read_only_tools(self):
        assert is_read_only("search_files") is True
        assert is_read_only("read_file") is True
        assert is_read_only("web_search") is True
        assert is_read_only("web_extract") is True
        assert is_read_only("session_search") is True
        assert is_read_only("tool_search") is True
        assert is_read_only("vision_analyze") is True

    def test_side_effect_tools(self):
        assert is_read_only("write_file") is False
        assert is_read_only("patch") is False
        assert is_read_only("terminal") is False
        assert is_read_only("memory") is False
        assert is_read_only("cronjob") is False
        assert is_read_only("skill_manage") is False
        assert is_read_only("send_message") is False

    def test_unknown_tool_is_not_read_only(self):
        assert is_read_only("unknown_tool") is False


class TestParallelToolsEnabled:
    @patch.dict("os.environ", {}, clear=True)
    def test_default_off(self):
        assert parallel_tools_enabled() is False

    @patch.dict("os.environ", {"MIMIR_PARALLEL_TOOLS": "0"}, clear=True)
    def test_explicit_off(self):
        assert parallel_tools_enabled() is False

    @patch.dict("os.environ", {"MIMIR_PARALLEL_TOOLS": "1"}, clear=True)
    def test_explicit_on(self):
        assert parallel_tools_enabled() is True


def _run_dispatch(tool_calls, dispatcher):
    """Helper: run dispatch_all synchronously via asyncio.run()."""
    loop = asyncio.new_event_loop()
    executor = ThreadPoolExecutor(max_workers=4)
    try:
        return loop.run_until_complete(
            dispatch_all(tool_calls, executor, dispatcher, task_id="test")
        )
    finally:
        loop.close()
        executor.shutdown()


class TestDispatchAll:
    """Integration-style tests with mock tool dispatcher."""

    def test_all_read_only_parallel(self):
        """All tools are read-only -> run in parallel."""
        dispatcher = MagicMock(return_value='{"ok": true}')
        tool_calls = [
            {"id": "call_1", "type": "function", "function": {"name": "read_file", "arguments": '{"path": "/tmp/a"}'}},
            {"id": "call_2", "type": "function", "function": {"name": "web_search", "arguments": '{"query": "test"}'}},
            {"id": "call_3", "type": "function", "function": {"name": "session_search", "arguments": '{"query": "x"}'}},
        ]

        results = _run_dispatch(tool_calls, dispatcher)

        assert len(results) == 3
        assert results[0][0] == "read_file"
        assert results[1][0] == "web_search"
        assert results[2][0] == "session_search"
        assert dispatcher.call_count == 3

    def test_mixed_tools(self):
        """Mix of read-only and side-effect tools."""
        dispatcher = MagicMock(return_value='{"ok": true}')
        tool_calls = [
            {"id": "call_1", "type": "function", "function": {"name": "read_file", "arguments": '{"path": "/tmp/a"}'}},
            {"id": "call_2", "type": "function", "function": {"name": "write_file", "arguments": '{"path": "/tmp/b", "content": "x"}'}},
            {"id": "call_3", "type": "function", "function": {"name": "web_search", "arguments": '{"query": "test"}'}},
        ]

        results = _run_dispatch(tool_calls, dispatcher)

        assert len(results) == 3
        assert results[0][0] == "read_file"
        assert results[1][0] == "write_file"
        assert results[2][0] == "web_search"
        assert dispatcher.call_count == 3

    def test_all_serial(self):
        """All tools are side-effect -> run serially."""
        dispatcher = MagicMock(return_value='{"ok": true}')
        tool_calls = [
            {"id": "call_1", "type": "function", "function": {"name": "write_file", "arguments": '{"path": "/tmp/a"}'}},
            {"id": "call_2", "type": "function", "function": {"name": "terminal", "arguments": '{"command": "ls"}'}},
        ]

        results = _run_dispatch(tool_calls, dispatcher)

        assert len(results) == 2
        assert dispatcher.call_count == 2

    def test_single_tool_degenerates_to_serial(self):
        """Single tool call -> same behavior as serial dispatch."""
        dispatcher = MagicMock(return_value='{"ok": true}')
        tool_calls = [
            {"id": "call_1", "type": "function", "function": {"name": "write_file", "arguments": '{"path": "/tmp/a"}'}},
        ]

        results = _run_dispatch(tool_calls, dispatcher)

        assert len(results) == 1
        assert dispatcher.call_count == 1

    def test_side_effect_order_preserved(self):
        """Side-effect tools execute in original order."""
        call_order = []

        def tracking_dispatcher(name, args, tid):
            call_order.append(name)
            return '{"ok": true}'

        tool_calls = [
            {"id": "call_1", "type": "function", "function": {"name": "read_file", "arguments": '{"path": "/tmp/a"}'}},
            {"id": "call_2", "type": "function", "function": {"name": "write_file", "arguments": '{"path": "/tmp/b"}'}},
            {"id": "call_3", "type": "function", "function": {"name": "patch", "arguments": '{"path": "/tmp/c"}'}},
        ]

        _run_dispatch(tool_calls, tracking_dispatcher)

        # Serial tools should execute in order: write_file, then patch
        assert call_order[0] == "read_file"
        assert call_order[1] == "write_file"
        assert call_order[2] == "patch"


class TestRetryEnv:
    """B1 (2026-08-19 v2): retry 由独立 env MIMIR_PARALLEL_RETRY 控制（默认 1=启用）。"""

    def _flaky_dispatcher(self):
        calls = {"n": 0}

        def dispatcher(name, args, tid):
            calls["n"] += 1
            if calls["n"] == 1:
                raise RuntimeError("boom")
            return '{"ok": true}'

        return dispatcher, calls

    @patch.dict("os.environ", {"MIMIR_PARALLEL_RETRY": "1"}, clear=True)
    def test_retry_enabled_retries_failed_tool(self):
        dispatcher, calls = self._flaky_dispatcher()
        tool_calls = [{"id": "call_1", "type": "function", "function": {"name": "read_file", "arguments": '{"path": "/tmp/a"}'}}]
        _run_dispatch(tool_calls, dispatcher)
        assert calls["n"] == 2  # 失败 1 次 + 重试成功

    @patch.dict("os.environ", {"MIMIR_PARALLEL_RETRY": "0"}, clear=True)
    def test_retry_disabled_single_attempt(self):
        dispatcher, calls = self._flaky_dispatcher()
        tool_calls = [{"id": "call_1", "type": "function", "function": {"name": "read_file", "arguments": '{"path": "/tmp/a"}'}}]
        _run_dispatch(tool_calls, dispatcher)
        assert calls["n"] == 1  # 不重试
