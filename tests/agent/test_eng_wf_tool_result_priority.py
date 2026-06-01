"""ENG-WF-05: Tool result preservation tests.

Context: MimirAgentLoop does NOT trim or prioritize messages.
All roles (tool, user, assistant, system) accumulate without dropping.
These tests verify that tool results survive the loop unchanged.

If future trimming is added, these tests guard against tool-message loss.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

_AGENT_TESTS = Path(__file__).resolve().parent
if str(_AGENT_TESTS) not in sys.path:
    sys.path.insert(0, str(_AGENT_TESTS))

from agent.agent_loop import MimirAgentLoop


def echo_tool_schema():
    return {
        "type": "function",
        "function": {
            "name": "echo",
            "description": "Echo back the input text",
            "parameters": {
                "type": "object",
                "properties": {"text": {"type": "string"}},
                "required": ["text"],
            },
        },
    }


def test_tool_result_preserved_across_turns():
    """Tool result messages survive the loop and remain readable."""
    call_count = [0]

    async def chat_fn(messages):
        call_count[0] += 1
        # Turn 1: call echo tool
        if call_count[0] == 1:
            return type(
                "MockResponse",
                (),
                {
                    "choices": [
                        type(
                            "MockChoice",
                            (),
                            {
                                "message": type(
                                    "MockMsg",
                                    (),
                                    {
                                        "content": "",
                                        "tool_calls": [
                                            type(
                                                "MockTC",
                                                (),
                                                {
                                                    "id": "call_1",
                                                    "type": "function",
                                                    "function": type(
                                                        "MockFunc",
                                                        (),
                                                        {
                                                            "name": "echo",
                                                            "arguments": '{"text": "hello"}',
                                                        },
                                                    ),
                                                },
                                            )
                                        ],
                                    },
                                )()
                            },
                        )()
                    ],
                },
            )()
        # Turn 2: just reply
        return type(
            "MockResponse",
            (),
            {
                "choices": [
                    type(
                        "MockChoice",
                        (),
                        {
                            "message": type("MockMsg", (), {"content": "Done"})(),
                        },
                    )()
                ],
            },
        )()

    def dispatch(name, args, tc_id):
        return args.get("text", "")

    loop = MimirAgentLoop(
        model_call=chat_fn,
        tool_schemas=[echo_tool_schema()],
        valid_tool_names={"echo"},
        tool_dispatcher=dispatch,
        max_turns=3,
    )

    result = asyncio.run(
        loop.run([{"role": "user", "content": "test tool preservation"}])
    )

    # Tool result messages should be present
    tool_msgs = [m for m in result.messages if m.get("role") == "tool"]
    assert len(tool_msgs) >= 1, f"Expected ≥1 tool message, got {len(tool_msgs)}"
    # Tool content should contain "hello" (echoed back)
    tool_content = " ".join(str(m.get("content", "")) for m in tool_msgs)
    assert "hello" in tool_content


def test_tool_result_not_removed_by_nudges():
    """Nudge messages (memory/skill/intent) do not displace tool results."""
    call_count = [0]

    async def chat_fn(messages):
        call_count[0] += 1
        if call_count[0] == 1:
            return type(
                "MockResponse",
                (),
                {
                    "choices": [
                        type(
                            "MockChoice",
                            (),
                            {
                                "message": type(
                                    "MockMsg",
                                    (),
                                    {
                                        "content": "",
                                        "tool_calls": [
                                            type(
                                                "MockTC",
                                                (),
                                                {
                                                    "id": "call_1",
                                                    "type": "function",
                                                    "function": type(
                                                        "MockFunc",
                                                        (),
                                                        {
                                                            "name": "echo",
                                                            "arguments": '{"text": "ping"}',
                                                        },
                                                    ),
                                                },
                                            )
                                        ],
                                    },
                                )()
                            },
                        )()
                    ],
                },
            )()
        return type(
            "MockResponse",
            (),
            {
                "choices": [
                    type(
                        "MockChoice",
                        (),
                        {
                            "message": type("MockMsg", (), {"content": "Done"})(),
                        },
                    )()
                ],
            },
        )()

    def dispatch(name, args, tc_id):
        return args.get("text", "")

    loop = MimirAgentLoop(
        model_call=chat_fn,
        tool_schemas=[echo_tool_schema()],
        valid_tool_names={"echo"},
        tool_dispatcher=dispatch,
        max_turns=3,
    )

    # Pre-populate nudges (as if previous turns had injected them)
    msgs = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "[memory-nudge] Remember X"},
        {"role": "user", "content": "[skill-nudge] Use Y skill"},
        {"role": "user", "content": "test tool with nudges"},
    ]

    result = asyncio.run(loop.run(msgs))

    # tool messages should still be there despite nudges in history
    tool_msgs = [m for m in result.messages if m.get("role") == "tool"]
    assert len(tool_msgs) >= 1, f"Expected ≥1 tool message, got {len(tool_msgs)}"
    tool_content = " ".join(str(m.get("content", "")) for m in tool_msgs)
    assert "ping" in tool_content
