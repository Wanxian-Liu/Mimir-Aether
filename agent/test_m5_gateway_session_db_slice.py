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
