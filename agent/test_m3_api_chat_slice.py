"""
M3 vertical slice #2: OpenAI-shaped HTTP → MimirAetherAgent.run_conversation.

No network: stubs _call_model_with_tokens. Checkpoints isolated under tmp_path.
Entry: POST /v1/chat/completions via aiohttp TestClient on api_service.create_app().
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture
def isolate_checkpoints(tmp_path, monkeypatch):
    import checkpoint_manager

    mgr = checkpoint_manager.CheckpointManager(checkpoint_dir=tmp_path / "m3_api_ckpt")
    monkeypatch.setattr(checkpoint_manager, "_checkpoint_manager", mgr)


def _reset_agent_manager() -> None:
    import api_service

    api_service.AgentManager._instance = None


def test_m3_api_health_get():
    _reset_agent_manager()

    async def _run():
        from aiohttp.test_utils import TestClient, TestServer
        from api_service import create_app

        app = create_app()
        server = TestServer(app)
        client = TestClient(server)
        await client.start_server()
        try:
            resp = await client.get("/health")
            assert resp.status == 200
            data = await resp.json()
            assert data.get("status") == "ok"
            assert data.get("service") == "MimirAether"
        finally:
            await client.close()

    asyncio.run(_run())


def test_m3_api_chat_completions_non_stream_stubbed(isolate_checkpoints):
    """POST /v1/chat/completions (stream=false) returns OpenAI-shaped JSON from stubbed LLM."""
    from agent.core_loop import MimirAetherAgent

    _reset_agent_manager()

    async def fake_llm(self, messages, session_id):
        assert any(
            m.get("role") == "user" and "m3 api slice" in (m.get("content") or "") for m in messages
        )
        return (
            {"content": "M3 API slice OK.", "tool_calls": None, "reasoning_content": None},
            0.05,
        )

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
                    "model": "m3-api-test",
                    "messages": [{"role": "user", "content": "ping m3 api slice"}],
                    "stream": False,
                },
            )
            assert resp.status == 200
            data = await resp.json()
            assert data["object"] == "chat.completion"
            assert data["model"] == "m3-api-test"
            assert data["choices"][0]["message"]["role"] == "assistant"
            assert "M3 API slice OK" in (data["choices"][0]["message"]["content"] or "")
            assert "usage" in data
        finally:
            await client.close()

    with patch.object(MimirAetherAgent, "_restore_session", lambda self, session_id=None: False):
        with patch.object(MimirAetherAgent, "_call_model_with_tokens", new=fake_llm):
            asyncio.run(_run())
