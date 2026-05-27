"""Grain A: /new and /reset await pre-reset memory flush."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from gateway.run import GatewayRunner


class _FlushHost(GatewayRunner):
    """Minimal host for flush-await helpers (no full gateway init)."""

    def __init__(self) -> None:
        pass


def test_manual_reset_awaits_flush_before_return():
    host = _FlushHost()
    host._async_flush_memories = AsyncMock()

    asyncio.run(host._await_flush_memories_for_manual_reset("sess-old", "feishu:dm:1"))

    host._async_flush_memories.assert_awaited_once_with("sess-old", "feishu:dm:1")


def test_manual_reset_flush_timeout_proceeds():
    host = _FlushHost()

    async def _slow_flush(*_a, **_k):
        await asyncio.sleep(10)

    host._async_flush_memories = _slow_flush

    with patch.object(GatewayRunner, "_reset_flush_timeout_sec", return_value=0.05):
        asyncio.run(host._await_flush_memories_for_manual_reset("sess-old", None))


def test_handle_reset_command_awaits_flush():
    from gateway.router.session_commands_mixin import SessionCommandsMixin

    class _Runner(SessionCommandsMixin):
        def __init__(self) -> None:
            self.session_store = MagicMock()
            self._agent_cache = {}
            self._agent_cache_lock = None
            self._session_model_overrides = {}
            self._background_tasks = set()
            self.hooks = MagicMock()
            self.hooks.emit = AsyncMock()
            self._await_flush = AsyncMock()

        def _session_key_for_source(self, source):
            return "k1"

        async def _await_flush_memories_for_manual_reset(self, sid, key):
            await self._await_flush(sid, key)

        def _evict_cached_agent(self, _key):
            pass

        def _format_session_info(self):
            return ""

    async def _run():
        runner = _Runner()
        old = MagicMock(session_id="old-sid")
        runner.session_store._entries = {"k1": old}
        runner.session_store.reset_session.return_value = MagicMock(session_id="new-sid")

        event = MagicMock()
        event.source = MagicMock()
        event.source.platform.value = "feishu"

        with patch("mimir_cli.plugins.invoke_hook"):
            with patch("tools.env_passthrough.clear_env_passthrough"):
                with patch("tools.credential_files.clear_credential_files"):
                    with patch("mimir_cli.tips.get_random_tip", return_value="tip"):
                        await runner._handle_reset_command(event)

        runner._await_flush.assert_awaited_once_with("old-sid", "k1")
        runner.session_store.reset_session.assert_called_once_with("k1")

    asyncio.run(_run())
