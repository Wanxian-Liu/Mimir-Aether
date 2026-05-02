"""
M5: CLI / API 入口注入 ``SessionRestorePort``（不跑真实对话）。

证明 ``session_backend`` 从 ``run_task`` / ``AgentManager`` 传入 ``MimirAetherAgent``。
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Any, Dict, Optional
from unittest.mock import AsyncMock, patch

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture
def isolate_checkpoints(tmp_path, monkeypatch):
    import checkpoint_manager

    mgr = checkpoint_manager.CheckpointManager(checkpoint_dir=tmp_path / "m5_sess_inj_ckpt")
    monkeypatch.setattr(checkpoint_manager, "_checkpoint_manager", mgr)


def _reset_agent_manager() -> None:
    import api_service

    api_service.AgentManager._instance = None
    api_service.AgentManager.set_llm_backend_override(None)
    api_service.AgentManager.set_tool_backend_override(None)
    api_service.AgentManager.set_session_backend_override(None)
    api_service.AgentManager.set_session_db_factory_override(None)


class _SessionKwStub:
    def restore_after_init(self, session_id: Optional[str] = None) -> bool:
        return False


def test_cli_run_task_passes_session_backend_kw(isolate_checkpoints):
    import cli as cli_module

    from agent.core_loop import MimirAetherAgent

    captured: Dict[str, Any] = {}
    _orig_init = MimirAetherAgent.__init__

    def _wrap_init(self, *a, **kw):
        captured.clear()
        captured.update(kw)
        return _orig_init(self, *a, **kw)

    stub = _SessionKwStub()
    with patch.object(MimirAetherAgent, "__init__", _wrap_init):
        with patch.object(MimirAetherAgent, "run_conversation", new_callable=AsyncMock) as m_rc:
            m_rc.return_value = "skipped"
            rc = asyncio.run(
                cli_module.run_task(
                    "m5 session kw cli",
                    model="deepseek/deepseek-chat",
                    max_iterations=2,
                    verbose=False,
                    session_backend=stub,
                )
            )

    assert rc == 0
    assert captured.get("session_backend") is stub


def test_api_agent_manager_session_backend_override(isolate_checkpoints):
    from agent.core_loop import MimirAetherAgent
    from agent.session_port import SessionRestorePort

    _reset_agent_manager()

    class _ApiSessStub:
        def restore_after_init(self, session_id: Optional[str] = None) -> bool:
            return False

    import api_service

    api_service.AgentManager.set_session_backend_override(_ApiSessStub())

    async def _run():
        mgr = api_service.AgentManager()
        ag = await mgr.get_agent("m5-session-override-session")
        assert isinstance(ag._session_backend, SessionRestorePort)
        assert isinstance(ag._session_backend, _ApiSessStub)

    asyncio.run(_run())

    _reset_agent_manager()


class _FactoryKwStub:
    def create_session_db(self):
        return None


def test_cli_run_task_passes_session_db_factory_kw(isolate_checkpoints):
    import cli as cli_module

    from agent.core_loop import MimirAetherAgent

    captured: Dict[str, Any] = {}
    _orig_init = MimirAetherAgent.__init__

    def _wrap_init(self, *a, **kw):
        captured.clear()
        captured.update(kw)
        return _orig_init(self, *a, **kw)

    stub = _FactoryKwStub()
    with patch.object(MimirAetherAgent, "__init__", _wrap_init):
        with patch.object(MimirAetherAgent, "run_conversation", new_callable=AsyncMock) as m_rc:
            m_rc.return_value = "skipped"
            rc = asyncio.run(
                cli_module.run_task(
                    "m5 factory kw cli",
                    model="deepseek/deepseek-chat",
                    max_iterations=2,
                    verbose=False,
                    session_db_factory=stub,
                )
            )

    assert rc == 0
    assert captured.get("session_db_factory") is stub


def test_api_agent_manager_session_db_factory_override(isolate_checkpoints):
    from agent.core_loop import MimirAetherAgent
    from agent.session_port import SessionDbClientFactory

    _reset_agent_manager()

    class _ApiFacStub:
        def create_session_db(self):
            return None

    import api_service

    api_service.AgentManager.set_session_db_factory_override(_ApiFacStub())

    async def _run():
        mgr = api_service.AgentManager()
        ag = await mgr.get_agent("m5-factory-override-session")
        assert isinstance(ag._session_db_factory, SessionDbClientFactory)
        assert isinstance(ag._session_db_factory, _ApiFacStub)

    asyncio.run(_run())

    _reset_agent_manager()
