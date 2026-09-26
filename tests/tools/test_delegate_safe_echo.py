"""Regression: the delegate progress line must not assume a live stdout.

Production evidence (logs/agent.log, 2026-09-14 23:37 and 23:44):
    ERROR tools.registry: Tool delegate_task dispatch error:
    I/O operation on closed file.
      File ".../tools/delegate_tool.py", line 844, in delegate_task

The gateway dispatches tools with stdout closed/redirected (non-TTY), so the
bare print() that emitted the per-task completion line raised ValueError and
aborted the whole delegation -- delegate_task could never succeed in-gateway.
"""
from __future__ import annotations

import importlib
import io
import logging
import pathlib
import sys

import pytest

mod = importlib.import_module("tools.delegate_tool")

LINE = "  \u2713 [1/3] Task  (1.2s)"


def _closed_stdout():
    buf = io.StringIO()
    buf.close()
    return buf


# --- control arm: prove the old shape really crashed ----------------------

def test_control_bare_print_with_closed_stdout_raises(monkeypatch):
    """The病形态 arm: without the fix this is exactly what production hit."""
    monkeypatch.setattr(sys, "stdout", _closed_stdout())
    with pytest.raises(ValueError) as ei:
        print("  x [1/3] Task  (1.2s)")
    assert "closed file" in str(ei.value)


# --- fixed behaviour ------------------------------------------------------

def test_safe_echo_survives_closed_stdout(monkeypatch):
    monkeypatch.setattr(sys, "stdout", _closed_stdout())
    mod._safe_echo(LINE)  # must not raise


def test_safe_echo_falls_back_to_logger(monkeypatch, caplog):
    monkeypatch.setattr(sys, "stdout", _closed_stdout())
    with caplog.at_level(logging.INFO, logger=mod.__name__):
        mod._safe_echo(LINE)
    assert any(LINE.strip() in (r.getMessage() or "") for r in caplog.records)


def test_safe_echo_prefers_stdout_when_alive(capsys):
    mod._safe_echo(LINE)
    assert LINE in capsys.readouterr().out


def test_safe_echo_is_exported_for_wiring():
    assert callable(getattr(mod, "_safe_echo", None))


# --- wiring guard: source level, so a revert cannot pass silently ---------

def test_progress_line_goes_through_safe_echo():
    src = pathlib.Path(mod.__file__).read_text(encoding="utf-8")
    assert src.count('_safe_echo(f"  {completion_line}")') == 2, (
        "both branches (spinner fallback + no-spinner) must use _safe_echo"
    )
    assert 'print(f"  {completion_line}")' not in src, (
        "bare print(f\"  {completion_line}\") reintroduced -> delegation aborts "
        "again with 'I/O operation on closed file'"
    )
