"""Tests for ToolDispatchContext (MW-03)."""

import re
import tempfile

import pytest

from agent.tool_dispatch_context import ToolDispatchContext


class TestToolDispatchContext:
    def test_valid_channels(self):
        """All specified channels should work."""
        ctx = ToolDispatchContext("sess_1", "cli", "/tmp")
        assert ctx.channel == "cli"

        ctx = ToolDispatchContext("sess_2", "feishu", "/tmp")
        assert ctx.channel == "feishu"

        ctx = ToolDispatchContext("sess_3", "api", "/tmp")
        assert ctx.channel == "api"

    def test_default_workspace_root_is_absolute(self):
        """Default workspace_root should be absolute path."""
        ctx = ToolDispatchContext("sess_1", "cli")
        assert ctx.workspace_root.startswith("/")

    def test_invalid_channel_raises(self):
        """Unknown channel should raise ValueError."""
        with pytest.raises(ValueError, match="Unknown channel"):
            ToolDispatchContext("sess_1", "discord", "/tmp")

    def test_relative_workspace_root_raises(self):
        """Relative workspace_root should raise ValueError."""
        with pytest.raises(ValueError, match="workspace_root must be absolute"):
            ToolDispatchContext("sess_1", "cli", "relative/path")

    def test_frozen_dataclass(self):
        """ToolDispatchContext should be immutable."""
        ctx = ToolDispatchContext("sess_1", "cli", "/tmp")
        with pytest.raises(AttributeError):
            ctx.session_id = "new_id"  # type: ignore[misc]

    def test_channel_pattern(self):
        """Session ID can be any string."""
        ctx = ToolDispatchContext("main:feishu:dm:oc_abc123", "feishu", "/tmp")
        assert ctx.channel == "feishu"
        assert "feishu" in ctx.session_id

    def test_real_workspace(self):
        """Works with a real directory path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            ctx = ToolDispatchContext("sess_1", "cli", tmpdir)
            assert ctx.workspace_root == tmpdir
