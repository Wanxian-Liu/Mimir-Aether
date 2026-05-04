"""
M5: Gateway SQLite session store injection via ``SessionDbClientFactory``.

``gateway.run.GatewayRunner(..., session_db_factory=…)`` uses the same protocol as
``MimirAetherAgent`` / ``InsightsEngine`` — ``create_session_db()`` → Hermes-compatible store.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


class _Fac:
    def __init__(self, db):
        self._db = db

    def create_session_db(self):
        return self._db


def test_gateway_runner_session_db_factory_injects_store():
    from gateway.run import GatewayRunner
    from gateway.config import load_gateway_config

    sentinel = object()
    runner = GatewayRunner(load_gateway_config(), session_db_factory=_Fac(sentinel))
    assert runner._session_db is sentinel


def test_gateway_runner_factory_none_yields_no_session_db():
    """Factory may intentionally return None (memory-only / tests)."""

    from gateway.run import GatewayRunner
    from gateway.config import load_gateway_config

    class _Null:
        def create_session_db(self):
            return None

    runner = GatewayRunner(load_gateway_config(), session_db_factory=_Null())
    assert runner._session_db is None


def test_session_store_append_dual_writes_sqlite(tmp_path):
    from unittest.mock import MagicMock

    from gateway.config import load_gateway_config
    from gateway.session import SessionStore

    db = MagicMock()
    store = SessionStore(
        tmp_path / "sessions",
        load_gateway_config(),
        transcript_session_db=db,
    )
    store.append_to_transcript("sid-1", {"role": "user", "content": "hello"})
    db.append_message.assert_called_once()
    kw = db.append_message.call_args[1]
    assert kw["session_id"] == "sid-1"
    assert kw["role"] == "user"
    assert kw["content"] == "hello"


def test_session_store_append_skip_db_skips_sqlite(tmp_path):
    from unittest.mock import MagicMock

    from gateway.config import load_gateway_config
    from gateway.session import SessionStore

    db = MagicMock()
    store = SessionStore(
        tmp_path / "sessions",
        load_gateway_config(),
        transcript_session_db=db,
    )
    store.append_to_transcript("sid-1", {"role": "user", "content": "x"}, skip_db=True)
    db.append_message.assert_not_called()


def test_gateway_runner_passes_session_db_to_session_store():
    from gateway.run import GatewayRunner
    from gateway.config import load_gateway_config

    sentinel = object()
    runner = GatewayRunner(load_gateway_config(), session_db_factory=_Fac(sentinel))
    assert runner.session_store._db is sentinel


def test_session_store_rewrite_transcript_clears_and_replays_sqlite(tmp_path):
    from unittest.mock import MagicMock

    from gateway.config import load_gateway_config
    from gateway.session import SessionStore

    db = MagicMock()
    store = SessionStore(
        tmp_path / "sessions",
        load_gateway_config(),
        transcript_session_db=db,
    )
    msgs = [
        {"role": "user", "content": "one"},
        {"role": "assistant", "content": "two"},
    ]
    store.rewrite_transcript("sid-rw", msgs)
    db.clear_messages.assert_called_once_with("sid-rw")
    assert db.append_message.call_count == 2
    roles = [db.append_message.call_args_list[i][1]["role"] for i in range(2)]
    assert roles == ["user", "assistant"]


def test_session_store_rewrite_skips_sqlite_without_clear_messages(tmp_path):
    from gateway.config import load_gateway_config
    from gateway.session import SessionStore

    class _AppendOnly:
        def __init__(self) -> None:
            self.appends: list = []

        def append_message(self, **kwargs):
            self.appends.append(kwargs)

    db = _AppendOnly()
    store = SessionStore(
        tmp_path / "sessions",
        load_gateway_config(),
        transcript_session_db=db,
    )
    store.rewrite_transcript("sid", [{"role": "user", "content": "x"}])
    assert db.appends == []
