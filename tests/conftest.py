"""Pytest-wide isolation: tier0 tests must not write to ~/.mimiraether."""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

import pytest

_DEFAULT_HOME = Path.home() / ".mimiraether"
_PROD_LOGS = _DEFAULT_HOME / "logs"


def _detach_handlers_under(log_dir: Path) -> list[logging.Handler]:
    log_dir = log_dir.resolve()
    root = logging.getLogger()
    removed: list[logging.Handler] = []
    for handler in list(root.handlers):
        if not isinstance(handler, RotatingFileHandler):
            continue
        try:
            base = Path(handler.baseFilename).resolve()
        except (OSError, ValueError):
            continue
        if base.parent == log_dir:
            root.removeHandler(handler)
            removed.append(handler)
    return removed


def pytest_sessionstart(session: pytest.Session) -> None:
    if _PROD_LOGS.is_dir():
        _detach_handlers_under(_PROD_LOGS)


@pytest.fixture(autouse=True)
def _isolate_mimir_test_runtime(monkeypatch, tmp_path):
    """Tmp home + strip file handlers bound to production logs/."""
    home = tmp_path / "mimir_aether_home"
    home.mkdir()
    monkeypatch.setenv("MIMIR_AETHER_HOME", str(home))
    monkeypatch.setenv("HERMES_HOME", str(home))
    monkeypatch.setenv("MIMIRAETHER_HOME", str(home))

    detached = _detach_handlers_under(_PROD_LOGS) if _PROD_LOGS.is_dir() else []
    yield
    root = logging.getLogger()
    for handler in detached:
        if handler not in root.handlers:
            root.addHandler(handler)
