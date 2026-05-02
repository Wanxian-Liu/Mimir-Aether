"""M5: SessionDbClientFactory unifies Insights + builtin transcript restore DB construction."""

from __future__ import annotations

from typing import Any, List, Optional

from agent.session_port import SessionDbClientFactory


class _CountFactory:
    def __init__(self) -> None:
        self.calls = 0

    def create_session_db(self) -> Optional[Any]:
        self.calls += 1
        return None


def test_count_factory_satisfies_protocol() -> None:
    f = _CountFactory()
    assert isinstance(f, SessionDbClientFactory)
    assert f.create_session_db() is None
    assert f.calls == 1


def test_agent_invokes_factory_for_insights_and_restore() -> None:
    from agent.core_loop import MimirAetherAgent

    fac = _CountFactory()
    MimirAetherAgent(
        session_db_factory=fac,
        max_iterations=2,
        platform="cli",
        model="deepseek/deepseek-chat",
    )
    # __init__: create_session_db for insights + end-of-init _restore_session → builtin restore
    assert fac.calls == 2


def test_builtin_restore_calls_factory() -> None:
    from unittest.mock import patch

    from agent import core_loop
    from agent.core_loop import MimirAetherAgent

    fac = _CountFactory()
    with patch.object(core_loop, "SessionDB", None):
        agent = MimirAetherAgent(
            session_db_factory=fac,
            max_iterations=2,
            platform="cli",
            model="deepseek/deepseek-chat",
        )
    # insights + init-time restore: 2 calls with SessionDB patched out
    assert fac.calls == 2
    agent._builtin_restore_session()
    assert fac.calls == 3


def test_insights_sql_mode_when_factory_returns_db_handle() -> None:
    class FakeDB:
        _conn = object()

        def export_all(self) -> List[dict]:
            return []

        def get_messages(self, session_id: str) -> List[dict]:
            return []

    class _Fac:
        def create_session_db(self) -> Optional[Any]:
            return FakeDB()

    from agent.core_loop import MimirAetherAgent

    agent = MimirAetherAgent(
        session_db_factory=_Fac(),
        max_iterations=2,
        platform="cli",
        model="deepseek/deepseek-chat",
    )
    assert agent.insights._is_sql_mode is True
    assert isinstance(agent.insights.db, FakeDB)
