"""Q23/Q24 — cron script dispatch must be shebang/suffix aware.

Follow-up to RS20 (same incident, second root cause).  The gateway used to
launch every cron `script` as::

    subprocess.Popen(["/bin/bash", str(script_path)], ...)

i.e. it *ignored the shebang*.  Job `6d82dd753060` pointed at
`mech_checks_cron.py`, so bash parsed Python:

* the first syntax error aborted the parse, but
* a backtick inside the module docstring was executed as a command
  substitution and spawned util-linux ``script``, which waits forever on a
  pty.

The job then burned the whole 300s cap and reported only ``timeout`` — a silent
misconfiguration, not a slow script.  Fix: resolve an explicit argv
(shebang > suffix map > refuse) and fail fast when the type is unknown.
"""
from __future__ import annotations

import pathlib
import sys

import pytest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from cron.jobs import (  # noqa: E402
    _SUFFIX_INTERPRETERS,
    resolve_script_argv,
    validate_script_config,
)


# --------------------------------------------------------------- resolution
def test_py_with_shebang_uses_the_shebang(tmp_path):
    p = tmp_path / "job.py"
    p.write_text("#!/usr/bin/env python3\nprint('hi')\n", encoding="utf-8")
    argv, reason = resolve_script_argv(p)
    assert reason is None
    assert argv == ["/usr/bin/env", "python3", str(p)]


def test_sh_without_shebang_falls_back_to_bash(tmp_path):
    p = tmp_path / "job.sh"
    p.write_text("echo hi\n", encoding="utf-8")
    argv, reason = resolve_script_argv(p)
    assert reason is None
    assert argv[0] == "/bin/bash"
    assert argv[-1] == str(p)


def test_py_without_shebang_uses_the_project_interpreter(tmp_path):
    p = tmp_path / "job.py"
    p.write_text("print('hi')\n", encoding="utf-8")
    argv, reason = resolve_script_argv(p)
    assert reason is None
    assert argv[0] == _SUFFIX_INTERPRETERS[".py"][0]
    assert argv[-1] == str(p)


def test_py_with_backtick_docstring_is_never_handed_to_bash(tmp_path):
    """The exact 05:37 trigger: backticks in a .py docstring."""
    p = tmp_path / "hazard.py"
    p.write_text('"""Docs with a `script` backtick."""\nprint("done")\n', encoding="utf-8")
    argv, reason = resolve_script_argv(p)
    assert reason is None
    assert argv[0] != "/bin/bash", "regression: .py must not be parsed by bash"


def test_unknown_suffix_is_refused(tmp_path):
    p = tmp_path / "job.txt"
    p.write_text("whatever\n", encoding="utf-8")
    argv, reason = resolve_script_argv(p)
    assert argv is None
    assert "unsupported cron script type" in reason


def test_extensionless_script_is_refused(tmp_path):
    p = tmp_path / "job"
    p.write_text("whatever\n", encoding="utf-8")
    argv, reason = resolve_script_argv(p)
    assert argv is None
    assert "<no extension>" in reason


def test_missing_file_is_refused(tmp_path):
    argv, reason = resolve_script_argv(tmp_path / "nope.py")
    assert argv is None
    assert "unreadable" in reason


def test_empty_shebang_is_refused(tmp_path):
    p = tmp_path / "job.sh"
    p.write_text("#!\necho hi\n", encoding="utf-8")
    argv, reason = resolve_script_argv(p)
    assert argv is None
    assert reason == "malformed shebang"


# ---------------------------------------------- Q24 creation-time validation
@pytest.mark.parametrize("name", ["a.sh", "a.bash", "a.py", "a.js"])
def test_validate_accepts_dispatchable_suffixes(name):
    assert validate_script_config(name) is None


@pytest.mark.parametrize("name", ["a.txt", "a", "a.ts"])
def test_validate_rejects_undispatchable_suffixes(name):
    reason = validate_script_config(name)
    assert reason is not None
    assert "unsupported cron script type" in reason


# ------------------------------------- wiring: the gateway must use the resolver
def test_cron_mixin_no_longer_hardcodes_bash():
    src = (REPO_ROOT / "gateway" / "cron_mixin.py").read_text(encoding="utf-8")
    assert '["/bin/bash", str(script_path)]' not in src
    assert "resolve_script_argv(script_path)" in src
    assert "cannot dispatch cron script" in src
