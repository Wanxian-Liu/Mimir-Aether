"""M5: CLI/API inject ``checkpoint_backend`` into ``MimirAetherAgent``."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Any, Dict
from unittest.mock import AsyncMock, patch

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture
def isolate_checkpoints(tmp_path, monkeypatch):
    import checkpoint_manager

    mgr = checkpoint_manager.CheckpointManager(checkpoint_dir=tmp_path / "m5_ckpt_inj")
    monkeypatch.setattr(checkpoint_manager, "_checkpoint_manager", mgr)


def _reset_agent_manager() -> None:
    import api_service

    api_service.AgentManager._instance = None
    api_service.AgentManager.set_llm_backend_override(None)
    api_service.AgentManager.set_tool_backend_override(None)
    api_service.AgentManager.set_session_backend_override(None)
    api_service.AgentManager.set_session_db_factory_override(None)
    api_service.AgentManager.set_checkpoint_backend_override(None)


class _CkptKwStub:
    def load_checkpoint(self, task_id: str):
        return None

    def save_checkpoint(self, task_id, state, current_step=0, next_action="继续执行"):
        return True

    def clear_checkpoint(self, task_id: str):
        return True


def test_cli_run_task_passes_checkpoint_backend_kw(isolate_checkpoints):
    import cli as cli_module

    from agent.core_loop import MimirAetherAgent

    captured: Dict[str, Any] = {}
    _orig_init = MimirAetherAgent.__init__

    def _wrap_init(self, *a, **kw):
        captured.clear()
        captured.update(kw)
        return _orig_init(self, *a, **kw)

    stub = _CkptKwStub()
    with patch.object(MimirAetherAgent, "__init__", _wrap_init):
        with patch.object(MimirAetherAgent, "run_conversation", new_callable=AsyncMock) as m_rc:
            m_rc.return_value = "skipped"
            rc = asyncio.run(
                cli_module.run_task(
                    "m5 ckpt kw cli",
                    model="deepseek/deepseek-chat",
                    max_iterations=2,
                    verbose=False,
                    checkpoint_backend=stub,
                )
            )

    assert rc == 0
    assert captured.get("checkpoint_backend") is stub


def test_api_agent_manager_checkpoint_backend_override(isolate_checkpoints):
    from agent.checkpoint_port import CheckpointPersistencePort
    from agent.core_loop import MimirAetherAgent

    _reset_agent_manager()

    class _ApiCkptStub:
        def load_checkpoint(self, task_id: str):
            return None

        def save_checkpoint(self, task_id, state, current_step=0, next_action="继续执行"):
            return True

        def clear_checkpoint(self, task_id: str):
            return True

    import api_service

    api_service.AgentManager.set_checkpoint_backend_override(_ApiCkptStub())

    async def _run():
        mgr = api_service.AgentManager()
        ag = await mgr.get_agent("m5-ckpt-override-session")
        assert isinstance(ag._checkpoint_backend, CheckpointPersistencePort)
        assert isinstance(ag._checkpoint_backend, _ApiCkptStub)

    with patch.object(MimirAetherAgent, "_restore_session", lambda self, session_id=None: False):
        asyncio.run(_run())

    _reset_agent_manager()
