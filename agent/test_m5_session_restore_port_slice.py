"""M5: SessionRestorePort — transcript hydrate seam (no SessionDB required for protocol tests)."""

from __future__ import annotations

from typing import Optional
from unittest.mock import patch

from agent.session_port import SessionRestorePort


class _Stub:
    def restore_after_init(self, session_id: Optional[str] = None) -> bool:
        return True


def test_stub_satisfies_session_restore_port() -> None:
    s = _Stub()
    assert isinstance(s, SessionRestorePort)
    assert s.restore_after_init() is True
    assert s.restore_after_init("sid-1") is True


def test_missing_method_not_port() -> None:
    class Bad:
        pass

    assert not isinstance(Bad(), SessionRestorePort)


def test_init_invokes_injected_session_backend() -> None:
    class CountStub:
        calls = 0

        def restore_after_init(self, session_id: Optional[str] = None) -> bool:
            CountStub.calls += 1
            return False

    from agent.core_loop import MimirAetherAgent

    CountStub.calls = 0
    stub = CountStub()
    MimirAetherAgent(
        session_backend=stub,
        max_iterations=2,
        platform="cli",
        model="deepseek/deepseek-chat",
    )
    assert CountStub.calls == 1


def test_default_restore_matches_builtin_when_no_sessiondb() -> None:
    from agent import core_loop
    from agent.core_loop import MimirAetherAgent

    with patch.object(core_loop, "SessionDB", None):
        agent = MimirAetherAgent(max_iterations=2, platform="cli", model="deepseek/deepseek-chat")
        a = agent._builtin_restore_session()
        b = agent._restore_session()
        assert a is b is False
