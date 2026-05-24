"""STAB-01: AIAgent activity tracker for gateway inactivity watchdog."""

from __future__ import annotations

import asyncio
import time
from unittest.mock import patch

from run_agent import AIAgent, _ACTIVITY_HEARTBEAT_INTERVAL


def test_get_activity_summary_initialized():
    agent = AIAgent()
    summary = agent.get_activity_summary()
    assert summary["last_activity_desc"] == "initialized"
    assert summary["current_tool"] is None
    assert summary["api_call_count"] == 0
    assert summary["max_iterations"] == 90
    assert summary["seconds_since_activity"] >= 0


def test_step_callback_wrap_touches_activity():
    agent = AIAgent()
    calls: list[int] = []

    agent.step_callback = lambda iteration, _tools: calls.append(iteration)
    wrapped = agent._wrap_step_callback(agent.step_callback)
    assert wrapped is not None

    before = agent.get_activity_summary()["api_call_count"]
    wrapped(2, [{"name": "read_file"}])
    after = agent.get_activity_summary()

    assert calls == [2]
    assert after["api_call_count"] == before + 1
    assert after["last_activity_desc"] in ("iteration 2", "after tool read_file")


def test_tool_progress_wrap_sets_current_tool():
    agent = AIAgent()
    agent.tool_progress_callback = lambda tool_name, *_a, **_k: tool_name
    wrapped = agent._wrap_tool_progress_callback(agent.tool_progress_callback)
    assert wrapped is not None
    assert wrapped("grep") == "grep"
    assert agent.get_activity_summary()["current_tool"] == "grep"


def test_run_conversation_heartbeat_keeps_activity_fresh():
    agent = AIAgent()

    async def slow_turn(*_a, **_k):
        await asyncio.sleep(_ACTIVITY_HEARTBEAT_INTERVAL + 0.05)
        return "ok"

    fake = type("FakeAgent", (), {"run_conversation": slow_turn})()

    with patch.object(AIAgent, "_get_real_agent", return_value=fake):
        with patch("run_agent._ACTIVITY_HEARTBEAT_INTERVAL", 0.05):
            result = agent.run_conversation("hello")

    assert result["final_response"] == "ok"
    assert agent.get_activity_summary()["seconds_since_activity"] < 0.2
    assert agent.get_activity_summary()["last_activity_desc"] == "run_conversation end"
