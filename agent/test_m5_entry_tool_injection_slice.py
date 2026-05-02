"""
M5: CLI 入口注入 ``ToolInvocationPort``（不跑真实对话）。

与 ``test_m5_entry_llm_injection_slice`` 对称：证明 ``tool_backend`` 从 ``run_task`` 传入 ``MimirAetherAgent``。
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import AsyncMock, patch

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture
def isolate_checkpoints(tmp_path, monkeypatch):
    import checkpoint_manager

    mgr = checkpoint_manager.CheckpointManager(checkpoint_dir=tmp_path / "m5_tool_inj_ckpt")
    monkeypatch.setattr(checkpoint_manager, "_checkpoint_manager", mgr)


class _ToolKwStub:
    async def execute_tools(self, tool_calls: List[Dict[str, Any]], turn: int = 0):
        from agent.types import ToolResult

        return [ToolResult(tool_call_id="z", content="kw", is_error=False)]


def test_cli_run_task_passes_tool_backend_kw(isolate_checkpoints):
    import cli as cli_module

    from agent.core_loop import MimirAetherAgent

    captured: Dict[str, Any] = {}
    _orig_init = MimirAetherAgent.__init__

    def _wrap_init(self, *a, **kw):
        captured.clear()
        captured.update(kw)
        return _orig_init(self, *a, **kw)

    stub = _ToolKwStub()
    with patch.object(MimirAetherAgent, "__init__", _wrap_init):
        with patch.object(MimirAetherAgent, "_restore_session", lambda self, session_id=None: False):
            with patch.object(MimirAetherAgent, "run_conversation", new_callable=AsyncMock) as m_rc:
                m_rc.return_value = "skipped"
                rc = asyncio.run(
                    cli_module.run_task(
                        "m5 tool kw cli",
                        model="deepseek/deepseek-chat",
                        max_iterations=2,
                        verbose=False,
                        tool_backend=stub,
                    )
                )

    assert rc == 0
    assert captured.get("tool_backend") is stub


def _reset_agent_manager() -> None:
    import api_service

    api_service.AgentManager._instance = None
    api_service.AgentManager.set_llm_backend_override(None)
    api_service.AgentManager.set_tool_backend_override(None)
    api_service.AgentManager.set_session_backend_override(None)
    api_service.AgentManager.set_session_db_factory_override(None)


def test_api_agent_manager_tool_backend_override(isolate_checkpoints):
    from agent.core_loop import MimirAetherAgent
    from agent.tool_port import ToolInvocationPort

    _reset_agent_manager()

    class _ApiToolStub:
        async def execute_tools(self, tool_calls: List[Dict[str, Any]], turn: int = 0):
            from agent.types import ToolResult

            return []

    import api_service

    api_service.AgentManager.set_tool_backend_override(_ApiToolStub())

    async def _run():
        mgr = api_service.AgentManager()
        ag = await mgr.get_agent("m5-tool-override-session")
        assert isinstance(ag._tool_backend, ToolInvocationPort)
        assert isinstance(ag._tool_backend, _ApiToolStub)

    with patch.object(MimirAetherAgent, "_restore_session", lambda self, session_id=None: False):
        asyncio.run(_run())

    _reset_agent_manager()
