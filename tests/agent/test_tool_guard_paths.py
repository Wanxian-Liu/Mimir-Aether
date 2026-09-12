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


# ── D1 (2026-09-13) — non-path params that merely *look* like paths ─────────


def test_memory_target_enum_not_treated_as_path(tmp_path, monkeypatch):
    """POSITIVE: memory's `target` is a store enum ('memory'|'user') — no warning."""
    monkeypatch.setenv("MIMIR_BASE_DIR", str(tmp_path))
    monkeypatch.chdir(tmp_path)
    result = guard_tool_call(
        "memory", {"action": "add", "target": "memory", "content": "x"}
    )
    assert result.ok is True
    assert result.warnings == []
    assert not result.block_reason


def test_memory_target_not_blocked_when_cwd_outside_base(tmp_path, monkeypatch):
    """REGRESSION: outside the allowed base the pseudo-path used to BLOCK memory.

    Same call shape, cwd outside MIMIR_BASE_DIR: memory must pass while a real
    write_file path in that cwd is still blocked (negative control).
    """
    base = tmp_path / "base"
    base.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    monkeypatch.setenv("MIMIR_BASE_DIR", str(base))
    monkeypatch.chdir(outside)

    assert guard_tool_call("memory", {"target": "memory"}).ok is True
    assert guard_tool_call("memory", {"target": "user"}).ok is True

    blocked = guard_tool_call("write_file", {"path": "notes.txt"})
    assert blocked.ok is False
    assert "blocked by ToolGuard" in blocked.block_reason


def test_generic_path_name_matching_preserved_for_other_tools(tmp_path, monkeypatch):
    """NEGATIVE: the override is per-tool — other FILE_WRITE tools still warn."""
    monkeypatch.setenv("MIMIR_BASE_DIR", str(tmp_path))
    monkeypatch.chdir(tmp_path)
    result = guard_tool_call("patch", {"target": "notes.txt"})
    assert result.ok is True
    assert any("relative path" in w for w in result.warnings)
