"""Pytest-wide isolation + test harness for MimirAether.

- _isolate_mimir_test_runtime: tier0 tests must not write to ~/.mimiraether.
- harness fixture / create_mimir_harness(): unified factory for SessionDB + FauxLlm.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import pytest

from mimir_state import SessionDB

_DEFAULT_HOME = Path.home() / ".mimiraether"
_PROD_LOGS = _DEFAULT_HOME / "logs"


# ===========================================================================
# Production-log isolation (unchanged)
# ===========================================================================

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


# ===========================================================================
# FauxLlmProvider — lightweight mock LLM for tests
# ===========================================================================

class FauxLlmProvider:
    """Lightweight mock LLM that returns predefined responses in order.

    Matches the ``LlmInvocationPort`` protocol signature
    (``call_model_with_tokens(messages, session_id)``).

    Usage::

        faux = FauxLlmProvider()
        faux.set_responses([
            {"choices": [{"message": {"content": "hello"}}]},
            {"choices": [{"message": {"content": "world"}}]},
        ])
        response, latency = await faux.call_model_with_tokens([...], "s1")
    """

    def __init__(self) -> None:
        self._responses: List[Dict[str, Any]] = []
        self.call_count: int = 0

    def set_responses(self, responses: List[Dict[str, Any]]) -> None:
        """Replace all queued responses."""
        self._responses = list(responses)
        self.call_count = 0

    def append_responses(self, responses: List[Dict[str, Any]]) -> None:
        """Append to the response queue."""
        self._responses.extend(responses)

    async def call_model_with_tokens(
        self, messages: List[Dict[str, Any]], session_id: str
    ) -> tuple[Dict[str, Any], float]:
        """Return the next queued response, or a default no-op response."""
        self.call_count += 1
        if self.call_count <= len(self._responses):
            return self._responses[self.call_count - 1], 100.0
        return {"choices": [{"message": {"content": "(default faux reply)"}}]}, 100.0


# ===========================================================================
# Test harness
# ===========================================================================

@dataclass
class MimirHarness:
    """Unified test context for MimirAether tests.

    Usage::

        def test_foo(harness):
            harness.db.create_session("s1", source="test")
            harness.db.append_message("s1", role="user", content="hi")
            result = my_function(harness.db_path)
            assert result["ok"]
            # harness.cleanup() called automatically by fixture
    """

    tmp_path: Path
    """Temporary directory (isolated per test)."""

    db_path: Path
    """Path to the SessionDB SQLite database."""

    db: SessionDB
    """Ready-to-use SessionDB instance."""

    faux: FauxLlmProvider
    """Mock LLM provider (call_model_with_tokens)."""

    _cleanup_cbs: List[Callable[[], None]] = field(default_factory=list)

    def add_cleanup(self, cb: Callable[[], None]) -> None:
        """Register an additional cleanup callback."""
        self._cleanup_cbs.append(cb)

    def cleanup(self) -> None:
        """Close DB and run all cleanup callbacks."""
        try:
            self.db.close()
        except Exception:
            pass
        for cb in self._cleanup_cbs:
            try:
                cb()
            except Exception:
                pass


def create_mimir_harness(tmp_path: Path) -> MimirHarness:
    """Factory: build a fully-wired MimirHarness for the given tmp_path.

    Example::

        def test_my_feature(harness):
            # harness is already wired
            ...
    """
    db_path = tmp_path / "state.db"
    db = SessionDB(db_path=db_path)
    faux = FauxLlmProvider()
    return MimirHarness(
        tmp_path=tmp_path,
        db_path=db_path,
        db=db,
        faux=faux,
    )


@pytest.fixture
def harness(tmp_path: Path) -> MimirHarness:
    """Pytest fixture that provides a ready-to-use MimirHarness.

    Cleanup is automatic (fixture teardown calls ``harness.cleanup()``).
    """
    h = create_mimir_harness(tmp_path)
    yield h
    h.cleanup()


# ===========================================================================
# Echo-tool fixtures (moved up from tests/agent/conftest.py, 2026-08-15)
#
# Why: pytest 9.1.1 does not load tests/agent/conftest.py when a large mixed
# set of test paths (tests/, tests/agent/, tests/contract/, tests/gateway/,
# tests/tools/) is passed on one command line -> "fixture 'echo_tool_schema'
# not found".  tests/conftest.py IS loaded in that combination, so these
# fixtures now live here.  See docs/evolution_log.md M6 ralph-clear.
# ===========================================================================

import json  # noqa: E402

from agent.agent_loop import STRING_PARAM, tool_schema  # noqa: E402


@pytest.fixture
def echo_tool_schema():
    return tool_schema(
        "echo",
        "Echo back text",
        {
            "type": "object",
            "properties": {"text": STRING_PARAM},
            "required": ["text"],
        },
    )


@pytest.fixture
def register_echo_tool() -> Callable:
    def _register(loop) -> None:
        async def echo_handler(name, args, session_id):
            return json.dumps({"echo": args["text"]})

        loop.register_tool("echo", echo_handler)

    return _register
