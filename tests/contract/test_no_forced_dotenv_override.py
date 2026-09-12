"""Contract: no forced dotenv override on the user env file (2026-09-13 D-plan §②).

The B4-b failure had three clobber layers, all of which rewrote an explicitly
injected ``MIMIR_COMPRESS_THRESHOLD_TOKENS`` before the compressor read it:

1. systemd ``EnvironmentFile=`` (unit) beat the drop-in ``Environment=``  -> fixed by
   switching the drop-in to a *later* ``EnvironmentFile=`` (pinfile);
2. ``mimir_cli.env_loader.load_hermes_dotenv`` used ``override=True``       -> fixed by
   ``override=dotenv_should_override()`` (default: explicit injection wins);
3. ``gateway/agent_mixin.run_agent`` re-ran ``load_dotenv(_env_path, override=True)``
   on every turn, *before* the agent (and its compressor) was constructed -> fixed here.

This test locks layers 2 and 3 at the source-text level: a functional test would need
a live gateway, while the regression is a one-line ``override=True`` that no runtime
assertion covers. Companion runtime proof lives in
``~/.mimiraether/notes/2026-09-13-dplan-b4b-tri-state.md`` (``/proc/<pid>/environ``).
"""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


def test_agent_mixin_does_not_force_dotenv_override():
    text = _read("gateway/agent_mixin.py")
    assert "load_dotenv(_env_path, override=True" not in text, (
        "agent_mixin re-runs load_dotenv(override=True) per turn — it silently "
        "rewrites explicitly injected env keys before the agent is built"
    )
    assert "dotenv_should_override()" in text


def test_env_loader_user_env_is_not_force_overridden():
    text = _read("mimir_cli/env_loader.py")
    assert "override=True)" not in text, (
        "the user env file must not force-override the process environment"
    )
    assert "override=dotenv_should_override()" in text


def test_break_glass_is_documented():
    text = _read("mimir_cli/env_loader.py")
    assert "MIMIR_DOTENV_OVERRIDE_KEYS" in text


def test_runtime_default_is_injection_wins(monkeypatch, tmp_path):
    """Behavioural twin of the source checks above."""
    from mimir_cli.env_loader import load_hermes_dotenv

    (tmp_path / ".env").write_text(
        "MIMIR_COMPRESS_THRESHOLD_TOKENS=350000\n", encoding="utf-8")
    monkeypatch.delenv("MIMIR_DOTENV_OVERRIDE_KEYS", raising=False)
    monkeypatch.setenv("MIMIR_COMPRESS_THRESHOLD_TOKENS", "5000")
    load_hermes_dotenv(hermes_home=tmp_path)
    assert os.environ["MIMIR_COMPRESS_THRESHOLD_TOKENS"] == "5000"
