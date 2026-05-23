"""E-008 — task_runner compatibility with legacy ``import cli`` call sites."""

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

    mgr = checkpoint_manager.CheckpointManager(checkpoint_dir=tmp_path / "e008_ckpt")
    monkeypatch.setattr(checkpoint_manager, "_checkpoint_manager", mgr)


def test_cli_shim_reexports_run_task(isolate_checkpoints, capsys):
    import cli as cli_module

    async def fake_llm(self, messages, session_id):
        return (
            {
                "content": "E-008 shim reply.",
                "tool_calls": None,
                "reasoning_content": None,
            },
            0.1,
        )

    from agent.core_loop import MimirAetherAgent

    with patch.object(MimirAetherAgent, "_restore_session", lambda self, session_id=None: False):
        with patch.object(MimirAetherAgent, "_call_model_with_tokens", new=fake_llm):
            rc = asyncio.run(
                cli_module.run_task(
                    "e008 check",
                    model="deepseek/deepseek-chat",
                    max_iterations=4,
                    verbose=False,
                )
            )

    assert rc == 0
    assert "E-008 shim reply." in capsys.readouterr().out


def test_task_runner_matches_cli_shim_exports():
    import cli
    from mimir_cli import task_runner

    assert cli.run_task is task_runner.run_task
    assert cli.run_interactive is task_runner.run_interactive
