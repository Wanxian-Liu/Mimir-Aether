"""M5: ToolInvocationPort replaceability seam (no network)."""

from __future__ import annotations

import asyncio
from typing import Any, Dict, List
from unittest.mock import patch

from agent.tool_port import ToolInvocationPort
from agent.types import ToolResult, _get_tool_id


class _StubA:
    async def execute_tools(self, tool_calls: List[Dict[str, Any]], turn: int = 0) -> List[ToolResult]:
        return [
            ToolResult(
                tool_call_id=_get_tool_id(tc) or "u",
                content="A",
                is_error=False,
            )
            for tc in tool_calls
        ]


def test_stub_satisfies_tool_invocation_port() -> None:
    async def _run() -> None:
        s = _StubA()
        assert isinstance(s, ToolInvocationPort)
        out = await s.execute_tools(
            [{"type": "function", "id": "x", "function": {"name": "t", "arguments": {}}}],
            0,
        )
        assert len(out) == 1 and out[0].content == "A"

    asyncio.run(_run())


def test_missing_method_not_port() -> None:
    class Bad:
        pass

    assert not isinstance(Bad(), ToolInvocationPort)


def test_agent_injected_tool_backend() -> None:
    class Echo:
        async def execute_tools(self, tool_calls: List[Dict[str, Any]], turn: int = 0) -> List[ToolResult]:
            return [
                ToolResult(
                    tool_call_id=_get_tool_id(tc) or "e",
                    content="injected-tools",
                    is_error=False,
                )
                for tc in tool_calls
            ]

    from agent.core_loop import MimirAetherAgent

    with patch.object(MimirAetherAgent, "_restore_session", lambda self, session_id=None: False):
        agent = MimirAetherAgent(
            tool_backend=Echo(),
            max_iterations=2,
            platform="cli",
            model="deepseek/deepseek-chat",
        )

    async def _run() -> None:
        dummy = {
            "type": "function",
            "id": "call-1",
            "function": {"name": "noop", "arguments": "{}"},
        }
        out = await agent._execute_tools([dummy], 0)
        assert len(out) == 1 and out[0].content == "injected-tools"

    asyncio.run(_run())


def test_builtin_and_port_empty_agree() -> None:
    from agent.core_loop import MimirAetherAgent

    with patch.object(MimirAetherAgent, "_restore_session", lambda self, session_id=None: False):
        agent = MimirAetherAgent(max_iterations=2, platform="cli", model="deepseek/deepseek-chat")

    async def _run() -> None:
        a = await agent._execute_tools([], 0)
        b = await agent._builtin_execute_tools([], 0)
        assert a == b == []

    asyncio.run(_run())
