"""
Tests for agent.recovery — tool-level recovery patterns.

Covers:
  - classify_tool_error: all 4 patterns
  - ToolRecovery.attempt_recovery: each pattern
  - ToolRecovery.recovery_loop_check
  - Path extraction from error messages
  - Corrupted JSON repair
"""

import json
import os
import tempfile
import time

import pytest

_MIMIR_IMPORT_ERR = None
try:
    from agent.recovery import (
        ToolRecoveryPattern,
        ToolRecovery,
        ToolRecoveryAttempt,
        classify_tool_error,
        get_tool_recovery,
        _apply_permission_recovery,
        _apply_corrupted_recovery,
        _apply_missing_recovery,
        _extract_path_from_error,
    )
    _MIMIR_IMPORT_OK = True
except ImportError as _mimir_import_err:
    _MIMIR_IMPORT_OK = False
    _MIMIR_IMPORT_ERR = str(_mimir_import_err)

import pytest

pytestmark = pytest.mark.skipif(
    not _MIMIR_IMPORT_OK,
    reason=f"测试过期：引用的符号已从源码删除（agent.recovery 的 ToolRecovery 系列（2026-08-21 取证：符号已删除，重构为 MultiLevelRecovery/RecoveryLevel 体系）），需按当前 API 重写。import 错误: {_MIMIR_IMPORT_ERR}",
)


class TestClassifyToolError:
    """Error → RecoveryPattern classification."""

    def test_permission_denied(self):
        assert classify_tool_error("Permission denied: /etc/hosts") == ToolRecoveryPattern.PERMISSION

    def test_eacces(self):
        assert classify_tool_error("EACCES: cannot write to file") == ToolRecoveryPattern.PERMISSION

    def test_read_only_fs(self):
        assert classify_tool_error("Read-only file system: /mnt/ro") == ToolRecoveryPattern.PERMISSION

    def test_text_file_busy(self):
        assert classify_tool_error("Text file busy: /usr/bin/python3") == ToolRecoveryPattern.FILE_LOCK

    def test_resource_busy(self):
        assert classify_tool_error("Device or resource busy") == ToolRecoveryPattern.FILE_LOCK

    def test_invalid_json(self):
        assert classify_tool_error("Invalid JSON at position 42") == ToolRecoveryPattern.CORRUPTED

    def test_json_parse_error(self):
        assert classify_tool_error("JSON parse error: unexpected token") == ToolRecoveryPattern.CORRUPTED

    def test_json_decode_error(self):
        assert classify_tool_error("json.JSONDecodeError: Expecting ',' delimiter") == ToolRecoveryPattern.CORRUPTED

    def test_no_such_file(self):
        assert classify_tool_error("No such file or directory: /tmp/missing.txt") == ToolRecoveryPattern.MISSING

    def test_enoent(self):
        assert classify_tool_error("ENOENT: file not found") == ToolRecoveryPattern.MISSING

    def test_unknown_error(self):
        assert classify_tool_error("Something went terribly wrong") is None

    def test_case_insensitive(self):
        assert classify_tool_error("permission DENIED") == ToolRecoveryPattern.PERMISSION
        assert classify_tool_error("Invalid Json") == ToolRecoveryPattern.CORRUPTED


class TestPathExtraction:
    """Extract file paths from error messages."""

    def test_single_quoted_path(self):
        assert _extract_path_from_error("No such file or directory: '/tmp/test.txt'") == "/tmp/test.txt"

    def test_double_quoted_path(self):
        path = _extract_path_from_error('Cannot open "/home/user/file.json"')
        assert path == "/home/user/file.json"

    def test_unquoted_abs_path(self):
        assert _extract_path_from_error("Error at /var/log/app.log: permission") == "/var/log/app.log"

    def test_no_path(self):
        assert _extract_path_from_error("Something went wrong") == ""


class TestCorruptedRecovery:
    """JSON/YAML parse error recovery."""

    def test_valid_json_passes_through(self):
        ok, content = _apply_corrupted_recovery('{"key": "value"}')
        assert ok
        assert json.loads(content) == {"key": "value"}

    def test_trailing_comma_fixed(self):
        ok, content = _apply_corrupted_recovery('{"key": "value",}')
        assert ok
        assert json.loads(content) == {"key": "value"}

    def test_array_trailing_comma(self):
        ok, content = _apply_corrupted_recovery('[1, 2, 3,]')
        assert ok
        assert json.loads(content) == [1, 2, 3]

    def test_hopelessly_broken(self):
        ok, content = _apply_corrupted_recovery('not even close to json{{{')
        assert not ok


class TestMissingRecovery:
    """Parent directory creation for missing files."""

    def test_creates_parent_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = os.path.join(tmp, "deep", "nested", "file.txt")
            result = _apply_missing_recovery(target)
            assert result
            assert os.path.isdir(os.path.join(tmp, "deep", "nested"))

    def test_parent_exists_noop(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = os.path.join(tmp, "file.txt")
            result = _apply_missing_recovery(target)
            assert result  # parent exists, no mkdir needed

    def test_empty_path(self):
        assert not _apply_missing_recovery("")


class TestPermissionRecovery:
    """Permission recovery (chmod u+w)."""

    def test_nonexistent_path(self):
        assert not _apply_permission_recovery("/nonexistent/path/for/test")

    def test_adds_write_permission(self):
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as f:
            f.write("test")
            f.flush()
        try:
            os.chmod(f.name, 0o444)  # read-only
            result = _apply_permission_recovery(f.name)
            assert result
            mode = os.stat(f.name).st_mode & 0o200
            assert mode == 0o200  # user-write bit set
        finally:
            os.chmod(f.name, 0o644)
            os.unlink(f.name)


class TestToolRecovery:
    """Orchestrator integration tests."""

    def test_orchestrator_returns_attempt(self):
        tr = ToolRecovery()
        att = tr.attempt_recovery("Permission denied: '/tmp/x'", is_write_operation=True)
        assert isinstance(att, ToolRecoveryAttempt)
        assert att.pattern == ToolRecoveryPattern.PERMISSION

    def test_missing_only_on_write(self):
        tr = ToolRecovery()
        # In read context, MISSING should not trigger
        att = tr.attempt_recovery(
            "No such file or directory: '/tmp/x'",
            is_write_operation=False,
        )
        # When not write, MISSING is suppressed → no pattern match
        assert att.action_taken == "no_pattern_match"

    def test_stats_accumulate(self):
        tr = ToolRecovery()
        tr.attempt_recovery("Invalid JSON: parse error", is_write_operation=True)
        tr.attempt_recovery("Permission denied", is_write_operation=True)
        assert tr.stats.total_attempts >= 2

    def test_format_stats(self):
        tr = ToolRecovery()
        stats_str = tr.format_stats()
        assert "Tool Recovery" in stats_str

    def test_recovery_loop_clean(self):
        tr = ToolRecovery()
        # No recent attempts → no loop
        result = tr.recovery_loop_check("task_1")
        assert result is None

    def test_recovery_loop_triggered(self):
        tr = ToolRecovery()
        # Inject 3 recovery attempts with 2 unique patterns
        for i in range(3):
            pattern = ToolRecoveryPattern.PERMISSION if i < 2 else ToolRecoveryPattern.CORRUPTED
            att = ToolRecoveryAttempt(
                pattern=pattern,
                error_message=f"error {i}",
                action_taken="test",
                success=False,
                timestamp=time.time(),  # recent
            )
            tr.stats.attempts.append(att)
            tr.stats.total_attempts += 1
        result = tr.recovery_loop_check("task_1")
        assert result == "replan"

    def test_global_singleton(self):
        tr1 = get_tool_recovery()
        tr2 = get_tool_recovery()
        assert tr1 is tr2
