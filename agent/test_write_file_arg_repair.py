"""Unit tests for write_file argument repair (core_loop._parse_write_file_arguments_string)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent.core_loop import _parse_write_file_arguments_string  # noqa: E402


def test_parse_write_file_strict_json_round_trip():
    raw = json.dumps({"path": "/tmp/x", "content": "hello"}, ensure_ascii=False)
    out = _parse_write_file_arguments_string(raw)
    assert out == {"path": "/tmp/x", "content": "hello"}


def test_parse_write_file_regex_when_json_invalid():
    raw = 'not json {"path":"/data/out.txt","content":"line1\\nline2"}'
    out = _parse_write_file_arguments_string(raw)
    assert out is not None
    assert out["path"] == "/data/out.txt"
    assert "line1" in out["content"]


def test_parse_write_file_pipe_split():
    out = _parse_write_file_arguments_string("/abs/path/file.py|print(1)")
    assert out == {"path": "/abs/path/file.py", "content": "print(1)"}


def test_parse_write_file_pipe_split_empty_content():
    out = _parse_write_file_arguments_string("/only/path|")
    assert out["path"] == "/only/path"
    assert out["content"] == ""


def test_parse_write_file_double_escaped_inner_quotes():
    # Invalid JSON that becomes valid after un-escaping over-escaped quotes.
    broken = r'{"path":"/p","content":"say \\"hello\\" now"}'
    try:
        json.loads(broken)
        parsed_without_helper = True
    except json.JSONDecodeError:
        parsed_without_helper = False
    assert not parsed_without_helper
    out = _parse_write_file_arguments_string(broken)
    assert out is not None
    assert out["path"] == "/p"
    assert "hello" in out["content"]


def test_parse_write_file_returns_none_for_unrecoverable():
    assert _parse_write_file_arguments_string("@@@") is None
    assert _parse_write_file_arguments_string("") is None
    assert _parse_write_file_arguments_string("   ") is None
