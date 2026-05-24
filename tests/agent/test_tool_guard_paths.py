"""STAB-03 — ToolGuard path resolution and containment (tests/agent/)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent.tool_guard import (
    guard_tool_call,
    resolve_path_for_guard,
)
from tools.strategy import pre_validate_tool_call


def test_resolve_path_for_guard_relative_uses_cwd(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert resolve_path_for_guard("foo/bar.txt") == str(tmp_path / "foo" / "bar.txt")


def test_resolve_path_for_guard_absolute_unchanged(tmp_path):
    abs_path = str(tmp_path / "abs.txt")
    assert resolve_path_for_guard(abs_path) == abs_path


def test_relative_path_warns_but_allows(tmp_path, monkeypatch):
    monkeypatch.setenv("MIMIR_BASE_DIR", str(tmp_path))
    monkeypatch.chdir(tmp_path)
    result = guard_tool_call("write_file", {"path": "notes.txt"})
    assert result.ok is True
    assert any("relative path" in w for w in result.warnings)
    assert any("Resolved to" in w for w in result.warnings)


def test_traversal_outside_base_blocked(tmp_path, monkeypatch):
    monkeypatch.setenv("MIMIR_BASE_DIR", str(tmp_path))
    monkeypatch.chdir(tmp_path)
    result = guard_tool_call("write_file", {"path": "../../../etc/passwd"})
    assert result.ok is False
    assert "blocked by ToolGuard" in result.block_reason


def test_pre_validate_blocks_traversal(tmp_path, monkeypatch):
    monkeypatch.setenv("MIMIR_BASE_DIR", str(tmp_path))
    monkeypatch.chdir(tmp_path)
    pre = pre_validate_tool_call("write_file", {"path": "../../../etc/passwd"})
    assert pre.ok is False
    assert "tool_guard" in pre.checks_run
    assert "blocked by ToolGuard" in pre.error_message


def test_absolute_path_under_base_ok(tmp_path, monkeypatch):
    monkeypatch.setenv("MIMIR_BASE_DIR", str(tmp_path))
    target = tmp_path / "ok.txt"
    result = guard_tool_call("write_file", {"path": str(target)})
    assert result.ok is True
    assert not result.block_reason


def test_read_only_tool_skips_path_guard(tmp_path, monkeypatch):
    monkeypatch.setenv("MIMIR_BASE_DIR", str(tmp_path))
    monkeypatch.chdir(tmp_path)
    result = guard_tool_call("read_file", {"path": "../../../etc/passwd"})
    assert result.ok is True
    assert not result.warnings
