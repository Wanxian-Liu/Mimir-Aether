"""
EP-C01 — agent_loop integration tests (tests/agent/).

Three canonical loop paths with stub LLM (no network):
  1. Plain assistant reply, one turn
  2. Single tool call round-trip
  3. Unknown tool → structured tool error, loop continues
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

from agent.agent_loop import AgentResult, MimirAetherAgentLoop
from llm_mocks import MockChoice, MockMessage, MockResponse


def test_agent_loop_plain_reply_finishes_in_one_turn():
    async def chat_fn(messages):
        return MockResponse([MockChoice(MockMessage(content="你好，我是 Mimir。"))])

    loop = MimirAetherAgentLoop(chat_fn=chat_fn, tools=[], max_turns=5)
    result = asyncio.run(loop.run([{"role": "user", "content": "Hello"}]))

    assert isinstance(result, AgentResult)
    assert result.turns_used == 1
    assert result.finished_naturally is True
    assert result.tool_errors == []
    assert result.messages[-1]["content"] == "你好，我是 Mimir。"


def test_agent_loop_single_tool_call_round_trip(echo_tool_schema, register_echo_tool):
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
                            "arguments": json.dumps({"text": "hello"}),
                        },
                    }
                ]
            )
            return MockResponse([MockChoice(tc)])
        return MockResponse([MockChoice(MockMessage(content="Done!"))])

    loop = MimirAetherAgentLoop(
        chat_fn=chat_fn, tools=[echo_tool_schema], max_turns=5
    )
    register_echo_tool(loop)
    result = asyncio.run(loop.run([{"role": "user", "content": "echo test"}]))

    assert result.turns_used == 2
    assert result.finished_naturally is True
    assert result.tool_errors == []
    tool_msgs = [m for m in result.messages if m["role"] == "tool"]
    assert len(tool_msgs) == 1
    assert "hello" in tool_msgs[0]["content"]


def test_agent_loop_unknown_tool_records_error():
    call_count = [0]

    async def chat_fn(messages):
        call_count[0] += 1
        if call_count[0] == 1:
            tc = MockMessage(
                tool_calls=[
                    {
                        "id": "call_1",
                        "type": "function",
                        "function": {"name": "nonexistent", "arguments": "{}"},
                    }
                ]
            )
            return MockResponse([MockChoice(tc)])
        return MockResponse([MockChoice(MockMessage(content="Handled."))])

    loop = MimirAetherAgentLoop(chat_fn=chat_fn, tools=[], max_turns=5)
    result = asyncio.run(loop.run([{"role": "user", "content": "bad tool"}]))

    assert result.turns_used == 2
    assert len(result.tool_errors) == 1
    assert result.tool_errors[0].tool_name == "nonexistent"
    tool_msgs = [m for m in result.messages if m["role"] == "tool"]
    assert len(tool_msgs) == 1
    assert "error" in tool_msgs[0]["content"].lower()
