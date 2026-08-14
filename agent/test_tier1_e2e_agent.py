"""
Ralph Tier-1: minimal end-to-end through MimirAetherAgent.run_conversation.

Uses a stubbed _call_model_with_tokens (no network, no API keys).
Checkpoints go to a temp dir; session restore is disabled for determinism.
"""

from __future__ import annotations

import asyncio
import json
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

    mgr = checkpoint_manager.CheckpointManager(checkpoint_dir=tmp_path / "tier1_ckpt")
    monkeypatch.setattr(checkpoint_manager, "_checkpoint_manager", mgr)


def test_tier1_plain_assistant_reply(isolate_checkpoints):
    from agent.core_loop import MimirAetherAgent

    async def fake_llm(self, messages, session_id):
        assert any(m.get("role") == "user" and "hello tier1" in (m.get("content") or "") for m in messages)
        return (
            {"content": "Tier-1 synthetic reply.", "tool_calls": None, "reasoning_content": None},
            0.25,
        )

    agent = MimirAetherAgent(
        model="deepseek-chat",
        max_iterations=8,
        platform="tier1-test",
        system_prompt="You are a concise test assistant.",
        save_trajectories=False,
    )

    with patch.object(MimirAetherAgent, "_restore_session", lambda self, session_id=None: False):
        with patch.object(MimirAetherAgent, "_call_model_with_tokens", new=fake_llm):
            out = asyncio.run(agent.run_conversation("hello tier1"))

    assert "Tier-1 synthetic" in out


def test_tier1_tool_call_then_final_reply(isolate_checkpoints):
    from agent.core_loop import MimirAetherAgent
    from agent.types import ToolResult

    state = {"n": 0}

    async def fake_llm(self, messages, session_id):
        state["n"] += 1
        if state["n"] == 1:
            return (
                {
                    "content": "",
                    "tool_calls": [
                        {
                            "id": "call_tier1_1",
                            "type": "function",
                            "function": {
                                "name": "get_env",  # 默认 toolsets 内真实工具（resolve_enabled_tools 55 个）
                                "arguments": json.dumps({"key": "TEST"}),
                            },
                        }
                    ],
                    "reasoning_content": None,
                },
                0.1,
            )
        return (
            {"content": "Final answer after tool.", "tool_calls": None, "reasoning_content": None},
            0.1,
        )

    async def fake_execute(self, tool_call, turn=0):
        # mock _execute_single_tool（ExecMixin，契约返回单个 ToolResult）
        # 返回含写盘关键字 → "架构产出提示"判定 _has_written=True，不触发第 3 次 LLM 调用
        # （2026-08-15 Ralph 清债：pre-existing 第 8 失败根因修复）
        return ToolResult(
            tool_call_id=tool_call.get("id", "call_tier1_1"),
            content='{"ok": true, "note": "File written to /tmp/tier1.txt"}',
        )

    agent = MimirAetherAgent(
        model="deepseek-chat",
        max_iterations=8,
        platform="tier1-test",
        system_prompt="You are a test assistant.",
        save_trajectories=False,
    )

    with patch.object(MimirAetherAgent, "_restore_session", lambda self, session_id=None: False):
        with patch.object(MimirAetherAgent, "_call_model_with_tokens", new=fake_llm):
            with patch.object(MimirAetherAgent, "_execute_single_tool", new=fake_execute):
                out = asyncio.run(agent.run_conversation("use the tool please"))

    assert state["n"] == 2
    assert "Final answer after tool" in out
