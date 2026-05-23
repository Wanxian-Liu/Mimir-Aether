"""
EP-C02 — agent_loop boundary tests (tests/agent/).

Three edge paths with stub LLM (no network):
  1. Multi-tool single turn — serial execution + ordered tool messages (H06)
  2. Invalid JSON tool arguments — structured tool error
  3. max_turns budget — loop stops without finishing naturally
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

_AGENT_TESTS = Path(__file__).resolve().parent
if str(_AGENT_TESTS) not in sys.path:
    sys.path.insert(0, str(_AGENT_TESTS))

from agent.agent_loop import MimirAetherAgentLoop
from llm_mocks import MockChoice, MockMessage, MockResponse


def test_agent_loop_multi_tool_single_turn_order_preserved(
    echo_tool_schema, register_echo_tool
):
    call_count = [0]

    async def chat_fn(messages):
        call_count[0] += 1
        if call_count[0] == 1:
            tc = MockMessage(
                tool_calls=[
                    {
                        "id": "call_1",
                        "type": "function",
                        "function": {
                            "name": "echo",
                            "arguments": json.dumps({"text": "A"}),
                        },
                    },
                    {
                        "id": "call_2",
                        "type": "function",
                        "function": {
                            "name": "echo",
                            "arguments": json.dumps({"text": "B"}),
                        },
                    },
                ]
            )
            return MockResponse([MockChoice(tc)])
        return MockResponse([MockChoice(MockMessage(content="Done"))])

    loop = MimirAetherAgentLoop(
        chat_fn=chat_fn, tools=[echo_tool_schema], max_turns=5
    )
    register_echo_tool(loop)
    result = asyncio.run(loop.run([{"role": "user", "content": "multi"}]))

    tool_msgs = [m for m in result.messages if m["role"] == "tool"]
    assert len(tool_msgs) == 2
    assert "A" in tool_msgs[0]["content"]
    assert "B" in tool_msgs[1]["content"]
    assert result.turns_used == 2
    assert result.finished_naturally is True


def test_agent_loop_json_arguments_parse_error(echo_tool_schema, register_echo_tool):
    call_count = [0]

    async def chat_fn(messages):
        call_count[0] += 1
        if call_count[0] == 1:
            tc = MockMessage(
                tool_calls=[
                    {
                        "id": "call_1",
                        "type": "function",
                        "function": {
                            "name": "echo",
                            "arguments": "not-valid-json!!!",
                        },
                    }
                ]
            )
            return MockResponse([MockChoice(tc)])
        return MockResponse([MockChoice(MockMessage(content="Done"))])

    loop = MimirAetherAgentLoop(
        chat_fn=chat_fn, tools=[echo_tool_schema], max_turns=5
    )
    register_echo_tool(loop)
    result = asyncio.run(loop.run([{"role": "user", "content": "bad json"}]))

    assert len(result.tool_errors) >= 1
    err = result.tool_errors[0].error
    assert "JSON" in err or "Invalid" in err


def test_agent_loop_max_turns_stops_loop(echo_tool_schema, register_echo_tool):
    async def chat_fn(messages):
        tc = MockMessage(
            tool_calls=[
                {
                    "id": "call_1",
                    "type": "function",
                    "function": {
                        "name": "echo",
                        "arguments": json.dumps({"text": "x"}),
                    },
                }
            ]
        )
        return MockResponse([MockChoice(tc)])

    loop = MimirAetherAgentLoop(
        chat_fn=chat_fn, tools=[echo_tool_schema], max_turns=1
    )
    register_echo_tool(loop)
    result = asyncio.run(loop.run([{"role": "user", "content": "budget"}]))

    assert result.turns_used == 1
    assert result.finished_naturally is False
