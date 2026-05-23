"""Shared fixtures for tests/agent/ (EP-C01+)."""

from __future__ import annotations

import json
from typing import Callable

import pytest

from agent.agent_loop import STRING_PARAM, tool_schema


@pytest.fixture
def echo_tool_schema():
    return tool_schema(
        "echo",
        "Echo back text",
        {
            "type": "object",
            "properties": {"text": STRING_PARAM},
            "required": ["text"],
        },
    )


@pytest.fixture
def register_echo_tool() -> Callable:
    def _register(loop) -> None:
        async def echo_handler(name, args, session_id):
            return json.dumps({"echo": args["text"]})

        loop.register_tool("echo", echo_handler)

    return _register
