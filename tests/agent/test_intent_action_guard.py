"""Intent-action guard — block text-only deferrals on grounded tasks."""

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

from agent.intent_action_guard import (
    assistant_defers_or_fakes_completion,
    build_nudge_message,
    should_block_text_only_finish,
    task_requires_tool_grounding,
)
from agent.agent_loop import MimirAetherAgentLoop
from llm_mocks import MockChoice, MockMessage, MockResponse


def test_task_requires_tool_grounding_playbook():
    assert task_requires_tool_grounding("对齐playbook 勾选")
    assert task_requires_tool_grounding("你把playbook收尾啊")
    assert not task_requires_tool_grounding("你好，今天天气怎么样")


def test_assistant_defers_detection():
    assert assistant_defers_or_fakes_completion("先看看 Playbook 当前状态。")
    assert assistant_defers_or_fakes_completion("## ✅ Playbook 对齐完成")
    assert not assistant_defers_or_fakes_completion("已用 read_file 核对 §2c，差异如下：…")


def test_should_block_text_only_on_playbook_task():
    msgs = [{"role": "user", "content": "对齐playbook 勾选"}]
    assert should_block_text_only_finish(
        msgs, "先看看 Playbook。", has_tool_schemas=True
    )


def test_should_not_block_after_tools_used():
    msgs = [
        {"role": "user", "content": "对齐playbook 勾选"},
        {"role": "assistant", "content": "", "tool_calls": [{"id": "1", "type": "function", "function": {"name": "read_file", "arguments": "{}"}}]},
        {"role": "tool", "tool_call_id": "1", "content": "ok"},
    ]
    assert not should_block_text_only_finish(
        msgs, "§2c 已对齐，变更如下。", has_tool_schemas=True
    )


def test_nudge_message_mentions_playbook_path():
    assert "MIMIR_EV_L_INDUSTRIAL_LEARNING.md" in build_nudge_message()
    assert "PLAYBOOK.md" in build_nudge_message()


def test_agent_loop_nudges_deferred_playbook_task(echo_tool_schema, register_echo_tool):
    call_count = [0]

    async def chat_fn(messages):
        call_count[0] += 1
        if call_count[0] == 1:
            return MockResponse(
                [MockChoice(MockMessage(content="先看看 Playbook 当前状态。"))]
            )
        if call_count[0] == 2:
            tc = MockMessage(
                tool_calls=[
                    {
                        "id": "call_1",
                        "type": "function",
                        "function": {
                            "name": "echo",
                            "arguments": json.dumps({"text": "read-playbook"}),
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
    result = asyncio.run(
        loop.run([{"role": "user", "content": "对齐playbook 勾选"}])
    )

    assert call_count[0] >= 2
    assert any(m.get("role") == "tool" for m in result.messages)
    assert any(
        "[intent-action-guard]" in (m.get("content") or "")
        for m in result.messages
        if m.get("role") == "user"
    )
    assert result.finished_naturally is True
