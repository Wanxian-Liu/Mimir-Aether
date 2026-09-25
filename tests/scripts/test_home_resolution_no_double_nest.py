"""HOME double-nesting guards for the RS19 mech-checks family (2026-09-26).

Pre-fix failure: with ``HOME=~/.mimiraether`` (agent sandboxes do this) the
runner resolved its registry default to ``<root>/.mimiraether/data/ops/...``
and died with FileNotFoundError; two items resolved their DB/file paths the
same way and reported "unparseable" instead of PASS.

Each arm asserts the discriminating property directly: no resolved path may
contain a doubled ``.mimiraether/.mimiraether`` segment.
"""
from __future__ import annotations

import importlib.util
import os
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]


def _load(rel: str):
    spec = importlib.util.spec_from_file_location(rel.replace("/", "_"), REPO / rel)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _clean_env():
    e = {k: v for k, v in os.environ.items()
         if k not in ("MIMIR_HOME", "MIMIR_AETHER_HOME", "MIMIRAETHER_HOME")}
    return e


def _resolve_with(monkeypatch, home: str, extra: dict | None = None):
    import pathlib
    monkeypatch.setenv("HOME", home)
    for k in ("MIMIR_HOME", "MIMIR_AETHER_HOME", "MIMIRAETHER_HOME"):
        monkeypatch.delenv(k, raising=False)
    for k, v in (extra or {}).items():
        monkeypatch.setenv(k, v)
    monkeypatch.setattr(pathlib.Path, "home", staticmethod(lambda: pathlib.Path(home)))
    return pathlib


@pytest.mark.parametrize("home,expected", [
    ("/home/tester/.mimiraether", "/home/tester/.mimiraether"),
    ("/home/tester", "/home/tester/.mimiraether"),
])
def test_runner_home_default_never_doubles(monkeypatch, home, expected):
    mod = _load("scripts/run_mech_checks.py")
    _resolve_with(monkeypatch, home)
    got = mod._resolve_home_default()
    assert ".mimiraether/.mimiraether" not in str(got), got
    assert str(got) == expected


def test_runner_home_default_env_wins(monkeypatch):
    mod = _load("scripts/run_mech_checks.py")
    _resolve_with(monkeypatch, "/home/tester/.mimiraether",
                  {"MIMIR_AETHER_HOME": "/tmp/other-root"})
    assert str(mod._resolve_home_default()) == "/tmp/other-root"


@pytest.mark.parametrize("rel", [
    "scripts/check_fts_idempotency.py",
    "scripts/check_persistent_invariants.py",
])
@pytest.mark.parametrize("home", ["/home/tester/.mimiraether", "/home/tester"])
def test_checker_home_helper_never_doubles(monkeypatch, rel, home):
    mod = _load(rel)
    _resolve_with(monkeypatch, home)
    got = mod._mimir_home()
    assert ".mimiraether/.mimiraether" not in str(got), got
    assert str(got) == "/home/tester/.mimiraether"


def test_env_first_matches_prod_shape(monkeypatch):
    """MIMIR_HOME (what the runner exports to children) must be honoured."""
    for rel in ("scripts/check_fts_idempotency.py", "scripts/check_persistent_invariants.py"):
        mod = _load(rel)
        _resolve_with(monkeypatch, "/home/tester", {"MIMIR_HOME": "/tmp/mimir-root"})
        assert str(mod._mimir_home()) == "/tmp/mimir-root", rel


def test_health_check_script_resolves_home_without_doubling():
    """Behavioural arm for the bash probe (5th file in this family).

    Before the fix, ``HOME=~/.mimiraether`` made R4 look for
    ``<root>/.mimiraether/logs/agent.log`` and downgrade to WARN.
    """
    import os
    import subprocess

    root = "/home/tester/.mimiraether"
    env = dict(os.environ, HOME=root)
    for k in ("MIMIR_HOME", "MIMIR_AETHER_HOME", "MIMIRAETHER_HOME"):
        env.pop(k, None)
    r = subprocess.run(["bash", "scripts/mimir_health_check.sh", "--quick"],
                       cwd=REPO, capture_output=True, text=True, timeout=300, env=env)
    out = r.stdout + r.stderr
    assert ".mimiraether/.mimiraether" not in out, out[-600:]
    assert "[WARN] R4" not in out, out[-600:]
