"""Env-injection precedence tests (2026-09-13 D-plan step 2).

Regression background
---------------------
``load_hermes_dotenv()`` used ``override=True`` for the user env file, so the
``.env`` file always clobbered keys that had been *explicitly injected* into the
process environment by the launcher (systemd ``EnvironmentFile=`` / drop-in /
shell).  Production impact: a maintenance pin of
``MIMIR_COMPRESS_THRESHOLD_TOKENS=5000`` was silently rewritten to the ``.env``
value before the compressor read it, so the pin never took effect (B4-b).

New contract
------------
* Explicitly injected process env **wins** over ``.env``.
* ``.env`` still **fills** keys that are absent from the process env.
* ``MIMIR_DOTENV_OVERRIDE_KEYS=1`` is the break-glass that restores legacy
  behaviour (dotenv overrides process env) for operational emergencies.
* The runtime-home anchor (MIMIR_AETHER_HOME ...) is never relocated by dotenv
  (2026-09-12 bare-python3 index-pollution fix) — re-locked here.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

from mimir_cli.env_loader import load_hermes_dotenv


@pytest.fixture()
def home(tmp_path):
    (tmp_path / ".env").write_text(
        "MIMIR_COMPRESS_THRESHOLD_TOKENS=350000\n"
        "MIMIR_DPLAN_ONLY_IN_FILE=file-value\n"
        "MIMIR_AETHER_HOME=~/.mimiraether\n",
        encoding="utf-8",
    )
    return tmp_path


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    for k in (
        "MIMIR_COMPRESS_THRESHOLD_TOKENS",
        "MIMIR_DPLAN_ONLY_IN_FILE",
        "MIMIR_DOTENV_OVERRIDE_KEYS",
        "MIMIR_AETHER_HOME",
    ):
        monkeypatch.delenv(k, raising=False)


def test_explicit_process_env_wins_over_dotenv(home, monkeypatch):
    """The pin must survive the dotenv load — this is the B4-b regression."""
    monkeypatch.setenv("MIMIR_COMPRESS_THRESHOLD_TOKENS", "5000")
    load_hermes_dotenv(hermes_home=home)
    assert os.environ["MIMIR_COMPRESS_THRESHOLD_TOKENS"] == "5000"


def test_dotenv_still_fills_absent_keys(home):
    load_hermes_dotenv(hermes_home=home)
    assert os.environ["MIMIR_DPLAN_ONLY_IN_FILE"] == "file-value"
    assert os.environ["MIMIR_COMPRESS_THRESHOLD_TOKENS"] == "350000"


def test_break_glass_restores_legacy_override(home, monkeypatch):
    monkeypatch.setenv("MIMIR_DOTENV_OVERRIDE_KEYS", "1")
    monkeypatch.setenv("MIMIR_COMPRESS_THRESHOLD_TOKENS", "5000")
    load_hermes_dotenv(hermes_home=home)
    assert os.environ["MIMIR_COMPRESS_THRESHOLD_TOKENS"] == "350000"


def test_home_anchor_survives_dotenv(home, monkeypatch):
    """dotenv must not relocate the runtime root (2026-09-12 pollution fix)."""
    monkeypatch.setenv("MIMIR_AETHER_HOME", str(home))
    load_hermes_dotenv(hermes_home=home)
    assert os.environ["MIMIR_AETHER_HOME"] == str(home)
