"""
M3 vertical slice: CLI single-task path (run_task) → MimirAetherAgent.run_conversation.

No network: stubs _call_model_with_tokens. Checkpoints isolated under tmp_path.
Entry covered: cli.run_task (used by `python cli.py -q "..."`).
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

    mgr = checkpoint_manager.CheckpointManager(checkpoint_dir=tmp_path / "m3_ckpt")
    monkeypatch.setattr(checkpoint_manager, "_checkpoint_manager", mgr)


def test_m3_cli_run_task_prints_stubbed_reply(isolate_checkpoints, capsys):
    """`run_task` drives the same agent stack as `python cli.py -q` without subprocess."""
    import cli as cli_module

    async def fake_llm(self, messages, session_id):
        assert any(
            m.get("role") == "user" and "m3 slice" in (m.get("content") or "")
            for m in messages
        )
        return (
            {
                "content": "M3 vertical slice reply.",
                "tool_calls": None,
                "reasoning_content": None,
            },
            0.12,
        )

    from agent.core_loop import MimirAetherAgent

    with patch.object(MimirAetherAgent, "_restore_session", lambda self, session_id=None: False):
        with patch.object(MimirAetherAgent, "_call_model_with_tokens", new=fake_llm):
            rc = asyncio.run(
                cli_module.run_task(
                    "m3 slice check",
                    model="deepseek/deepseek-chat",
                    max_iterations=6,
                    verbose=False,
                )
            )

    assert rc == 0
    out = capsys.readouterr().out
    assert "M3 vertical slice reply." in out
    assert "m3 slice check" in out
