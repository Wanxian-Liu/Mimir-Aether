"""M5: CheckpointPersistencePort for run_conversation resume/save/clear."""

from __future__ import annotations

from typing import Any, Dict, Optional

from agent.checkpoint_port import CheckpointPersistencePort


class _Stub:
    def load_checkpoint(self, task_id: str) -> Optional[Any]:
        return None

    def save_checkpoint(
        self,
        task_id: str,
        state: Dict[str, Any],
        current_step: int = 0,
        next_action: str = "继续执行",
    ) -> bool:
        return True

    def clear_checkpoint(self, task_id: str) -> bool:
        return True


def test_stub_satisfies_checkpoint_persistence_port() -> None:
    s = _Stub()
    assert isinstance(s, CheckpointPersistencePort)


def test_missing_methods_not_port() -> None:
    class Bad:
        def load_checkpoint(self, task_id: str):
            return None

    assert not isinstance(Bad(), CheckpointPersistencePort)


def test_agent_uses_injected_checkpoint_backend() -> None:
    class Echo(_Stub):
        tag = "echo"

    from unittest.mock import patch

    from agent.core_loop import MimirAetherAgent

    stub = Echo()
    with patch.object(MimirAetherAgent, "_restore_session", lambda self, session_id=None: False):
        agent = MimirAetherAgent(
            checkpoint_backend=stub,
            max_iterations=2,
            platform="cli",
            model="deepseek/deepseek-chat",
        )

    assert agent._checkpoint_backend is stub
    assert isinstance(agent._checkpoint_backend, CheckpointPersistencePort)
