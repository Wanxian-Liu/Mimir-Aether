"""Helpers for loading Hermes .env files consistently across entrypoints."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
#: Runtime-root keys. A dotenv file must never *relocate* the runtime home: the home
#: anchors every other path, and this repo's env file carries
#: ``MIMIR_AETHER_HOME=~/.mimiraether`` — with ``override=True`` that silently replaced a
#: test sandbox home with the production root (2026-09-12 bare-python3 Gate2 wrote 800
#: fixture rows into the production search index and 703 vectors into the prod chroma).
_HOME_KEYS = ("MIMIR_AETHER_HOME", "MIMIRAETHER_HOME", "HERMES_HOME")

#: Break-glass for the 2026-09-13 precedence fix. ``load_hermes_dotenv`` now
#: loads the user env file with ``override=False`` so keys **explicitly
#: injected** by the launcher (systemd ``EnvironmentFile=`` / drop-in /
#: shell) survive; the file only fills absent keys. Set this truthy to
#: restore the legacy "dotenv wins over the process env" behaviour.
_DOTENV_FORCE_OVERRIDE_ENV = "MIMIR_DOTENV_OVERRIDE_KEYS"
_TRUTHY = ("1", "true", "yes", "on")


def dotenv_should_override() -> bool:
    """True when legacy dotenv-wins behaviour was explicitly re-enabled."""
    raw = (os.environ.get(_DOTENV_FORCE_OVERRIDE_ENV) or "").strip().lower()
    return raw in _TRUTHY


def _load_dotenv_with_fallback(path: Path, *, override: bool) -> None:
    try:
        load_dotenv(dotenv_path=path, override=override, encoding="utf-8")
    except UnicodeDecodeError:
        load_dotenv(dotenv_path=path, override=override, encoding="latin-1")


def _sanitize_env_file_if_needed(path: Path) -> None:
    """Pre-sanitize a .env file before python-dotenv reads it.

    python-dotenv does not handle corrupted lines where multiple
    KEY=VALUE pairs are concatenated on a single line (missing newline).
    This produces mangled values — e.g. a bot token duplicated 8×
    (see #8908).

    We delegate to ``mimir_cli.config._sanitize_env_lines`` which
    already knows all valid Hermes env-var names and can split
    concatenated lines correctly.
    """
    if not path.exists():
        return
    try:
        from mimir_cli.config import _sanitize_env_lines
    except ImportError:
        return  # early bootstrap — config module not available yet

    read_kw = {"encoding": "utf-8", "errors": "replace"}
    try:
        with open(path, **read_kw) as f:
            original = f.readlines()
        sanitized = _sanitize_env_lines(original)
        if sanitized != original:
            import tempfile
            fd, tmp = tempfile.mkstemp(
                dir=str(path.parent), suffix=".tmp", prefix=".env_"
            )
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    f.writelines(sanitized)
                    f.flush()
                    os.fsync(f.fileno())
                os.replace(tmp, path)
            except BaseException:
                try:
                    os.unlink(tmp)
                except OSError:
                    pass
                raise
    except Exception:
        pass  # best-effort — don't block gateway startup


def load_hermes_dotenv(
    *,
    hermes_home: str | os.PathLike | None = None,
    project_env: str | os.PathLike | None = None,
) -> list[Path]:
    """Load Hermes environment files with user config taking precedence.

    Behavior:
    - explicitly injected process env (systemd EnvironmentFile= / drop-in /
      shell) is **never** overwritten by the user env file; the file only
      fills absent keys (break-glass: MIMIR_DOTENV_OVERRIDE_KEYS=1).
    - project `.env` acts as a dev fallback and only fills missing values when
      the user env exists.
    - if no user env exists, the project `.env` also overrides stale shell vars.
    """
    loaded: list[Path] = []
    # Snapshot the runtime root *before* any file is read — it must survive the load.
    _home_anchor = {k: os.environ[k] for k in _HOME_KEYS if k in os.environ}

    if hermes_home:
        home_path = Path(hermes_home)
    else:
        from mimir_constants import get_mimir_home

        home_path = get_mimir_home()
    user_env = home_path / ".env"
    project_env_path = Path(project_env) if project_env else None

    # Fix corrupted .env files before python-dotenv parses them (#8908).
    if user_env.exists():
        _sanitize_env_file_if_needed(user_env)

    if user_env.exists():
        _load_dotenv_with_fallback(user_env, override=dotenv_should_override())
        loaded.append(user_env)

    if project_env_path and project_env_path.exists():
        _load_dotenv_with_fallback(project_env_path, override=not loaded)
        loaded.append(project_env_path)

    # dotenv files may fill *other* keys, but never move the runtime root (see _HOME_KEYS).
    for _key, _value in _home_anchor.items():
        os.environ[_key] = _value

    return loaded
