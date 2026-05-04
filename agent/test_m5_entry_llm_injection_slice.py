"""
M5: CLI / API 入口注入 ``LlmInvocationPort``（不 patch ``_call_model_with_tokens``）。

与 M3 切片并存：M3 仍用 patch 证明同栈；本文件证明 **llm_backend** 从入口贯通到 agent。
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture
def isolate_checkpoints(tmp_path, monkeypatch):
    import checkpoint_manager

    mgr = checkpoint_manager.CheckpointManager(checkpoint_dir=tmp_path / "m5_inj_ckpt")
    monkeypatch.setattr(checkpoint_manager, "_checkpoint_manager", mgr)


class _EntryStub:
    async def call_model_with_tokens(
        self, messages: List[Dict[str, Any]], session_id: str
    ) -> tuple[Dict[str, Any], float]:
        assert any(
            m.get("role") == "user" and "m5 entry inject" in (m.get("content") or "")
            for m in messages
        )
        return (
            {
                "content": "M5 entry inject OK.",
                "tool_calls": None,
                "reasoning_content": None,
            },
            0.1,
        )


def test_cli_run_task_accepts_llm_backend(isolate_checkpoints, capsys):
    import cli as cli_module

    from agent.core_loop import MimirAetherAgent

    with patch.object(MimirAetherAgent, "_restore_session", lambda self, session_id=None: False):
        rc = asyncio.run(
            cli_module.run_task(
                "m5 entry inject cli",
                model="deepseek/deepseek-chat",
                max_iterations=4,
                verbose=False,
                llm_backend=_EntryStub(),
            )
        )

    assert rc == 0
    out = capsys.readouterr().out
    assert "M5 entry inject OK." in out


def _reset_agent_manager() -> None:
    import api_service

    api_service.AgentManager._instance = None
    api_service.AgentManager.set_llm_backend_override(None)
    api_service.AgentManager.set_tool_backend_override(None)
    api_service.AgentManager.set_session_backend_override(None)
    api_service.AgentManager.set_session_db_factory_override(None)
    api_service.AgentManager.set_checkpoint_backend_override(None)
    api_service.AgentManager.set_kernel_overrides(None)


def test_api_agent_manager_llm_backend_override(isolate_checkpoints):
    from agent.core_loop import MimirAetherAgent

    _reset_agent_manager()

    class _ApiStub:
        async def call_model_with_tokens(
            self, messages: List[Dict[str, Any]], session_id: str
        ) -> tuple[Dict[str, Any], float]:
            assert any(
                m.get("role") == "user" and "m5 api inject" in (m.get("content") or "")
                for m in messages
            )
            return (
                {"content": "M5 API inject OK.", "tool_calls": None, "reasoning_content": None},
                0.2,
            )

    import api_service

    api_service.AgentManager.set_llm_backend_override(_ApiStub())

    async def _run():
        from aiohttp.test_utils import TestClient, TestServer
        from api_service import create_app

        app = create_app()
        server = TestServer(app)
        client = TestClient(server)
        await client.start_server()
        try:
            resp = await client.post(
                "/v1/chat/completions",
                json={
                    "model": "m5-inject-test",
                    "messages": [{"role": "user", "content": "ping m5 api inject"}],
                    "stream": False,
                },
            )
            assert resp.status == 200
            data = await resp.json()
            assert "M5 API inject OK" in (data["choices"][0]["message"]["content"] or "")
        finally:
            await client.close()

    with patch.object(MimirAetherAgent, "_restore_session", lambda self, session_id=None: False):
        asyncio.run(_run())

    _reset_agent_manager()
