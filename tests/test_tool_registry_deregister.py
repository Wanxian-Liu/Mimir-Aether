"""Tests for ToolRegistry.deregister() — normal, repeat, nonexistent, toolset cleanup."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.registry import ToolRegistry


# ── Fixtures ──────────────────────────────────────────────────────────────


def _check_true():
    return True


@pytest.fixture
def reg():
    r = ToolRegistry()
    r.register(
        name="tool_one",
        schema={"description": "first tool", "name": "tool_one", "parameters": {"type": "object", "properties": {}}},
        toolset="test-a",
        handler=lambda: "result_a",
        check_fn=_check_true,
    )
    r.register(
        name="tool_two",
        schema={"description": "second tool", "name": "tool_two", "parameters": {"type": "object", "properties": {}}},
        toolset="test-a",
        handler=lambda: "result_b",
        check_fn=_check_true,
    )
    r.register(
        name="tool_three",
        schema={"description": "third tool", "name": "tool_three", "parameters": {"type": "object", "properties": {}}},
        toolset="test-b",
        handler=lambda: "result_c",
        check_fn=_check_true,
    )
    return r


# ── Tests ─────────────────────────────────────────────────────────────────


class TestDeregister:
    """ToolRegistry.deregister() behavior."""

    def test_deregister_removes_tool(self, reg):
        assert reg._tools.get("tool_one") is not None
        reg.deregister("tool_one")
        assert reg._tools.get("tool_one") is None

    def test_deregister_nonexistent_does_not_raise(self, reg):
        reg.deregister("does_not_exist")  # no exception

    def test_deregister_twice_does_not_raise(self, reg):
        reg.deregister("tool_one")
        reg.deregister("tool_one")  # second call also no-op

    def test_deregister_last_tool_cleans_up_toolset_check(self, reg):
        # tool_three is the only tool in test-b
        assert "test-b" in reg._toolset_checks
        reg.deregister("tool_three")
        assert "test-b" not in reg._toolset_checks

    def test_deregister_not_last_keeps_toolset_check(self, reg):
        # tool_one has sibling tool_two in same toolset
        assert "test-a" in reg._toolset_checks
        reg.deregister("tool_one")
        assert "test-a" in reg._toolset_checks  # tool_two still there

    def test_remaining_tools_still_usable_after_deregister(self, reg):
        reg.deregister("tool_one")
        entry = reg._tools.get("tool_two")
        assert entry is not None
        result = entry.handler()
        assert result == "result_b"

    def test_deregister_all_tools_clears_toolset_check(self, reg):
        reg.deregister("tool_one")
        reg.deregister("tool_two")
        assert "test-a" not in reg._toolset_checks
