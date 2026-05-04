"""
M5: ``AgentKernelOverrides`` 打包注入与优先级。

- ``MimirAetherAgent``：显式构造参数 > bundle 同名字段。
- ``cli.run_task`` / ``api_service.AgentManager.get_agent``：显式 per-field 参数 / ``set_*_override`` > bundle。
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture
def isolate_checkpoints(tmp_path, monkeypatch):
    import checkpoint_manager

    mgr = checkpoint_manager.CheckpointManager(checkpoint_dir=tmp_path / "m5_ko_ckpt")
    monkeypatch.setattr(checkpoint_manager, "_checkpoint_manager", mgr)


def _reset_agent_manager() -> None:
    import api_service

    api_service.AgentManager._instance = None
    api_service.AgentManager.set_llm_backend_override(None)
    api_service.AgentManager.set_tool_backend_override(None)
    api_service.AgentManager.set_session_backend_override(None)
    api_service.AgentManager.set_session_db_factory_override(None)
    api_service.AgentManager.set_checkpoint_backend_override(None)
    api_service.AgentManager.set_kernel_overrides(None)


class _LlmTag:
    """LLM stub that echoes a tag in content for assertions."""

    def __init__(self, tag: str) -> None:
        self.tag = tag

    async def call_model_with_tokens(
        self, messages: List[Dict[str, Any]], session_id: str
    ) -> tuple[Dict[str, Any], float]:
        return (
            {
                "content": f"OK {self.tag}",
                "tool_calls": None,
                "reasoning_content": None,
            },
            0.1,
        )


def test_agent_kernel_overrides_applies_llm(isolate_checkpoints):
    from agent.core_loop import MimirAetherAgent
    from agent.kernel_overrides import AgentKernelOverrides

    with patch.object(MimirAetherAgent, "_restore_session", lambda self, session_id=None: False):
        ag = MimirAetherAgent(
            model="deepseek/deepseek-chat",
            max_iterations=2,
            platform="test",
            kernel_overrides=AgentKernelOverrides(llm_backend=_LlmTag("bundle")),
        )
    assert ag._llm_backend is not None
    assert getattr(ag._llm_backend, "tag", None) == "bundle"


def test_agent_explicit_llm_wins_over_kernel_overrides(isolate_checkpoints):
    from agent.core_loop import MimirAetherAgent
    from agent.kernel_overrides import AgentKernelOverrides

    a = _LlmTag("A")
    b = _LlmTag("B")
    with patch.object(MimirAetherAgent, "_restore_session", lambda self, session_id=None: False):
        ag = MimirAetherAgent(
            model="deepseek/deepseek-chat",
            max_iterations=2,
            platform="test",
            llm_backend=b,
            kernel_overrides=AgentKernelOverrides(llm_backend=a),
        )
    assert ag._llm_backend is b


def test_api_kernel_bundle_then_single_llm_override(isolate_checkpoints):
    from agent.core_loop import MimirAetherAgent

    _reset_agent_manager()
    import api_service

    from agent.kernel_overrides import AgentKernelOverrides

    api_service.AgentManager.set_kernel_overrides(AgentKernelOverrides(llm_backend=_LlmTag("bundle")))
    api_service.AgentManager.set_llm_backend_override(_LlmTag("override"))

    async def _run():
        mgr = api_service.AgentManager()
        ag = await mgr.get_agent("m5-ko-precedence")
        out = await ag._call_model_with_tokens([], "sid")
        assert "OK override" in (out[0].get("content") or "")

    with patch.object(MimirAetherAgent, "_restore_session", lambda self, session_id=None: False):
        asyncio.run(_run())

    _reset_agent_manager()


def test_cli_run_task_accepts_kernel_overrides(isolate_checkpoints, capsys):
    import cli as cli_module
    from agent.core_loop import MimirAetherAgent
    from agent.kernel_overrides import AgentKernelOverrides

    with patch.object(MimirAetherAgent, "_restore_session", lambda self, session_id=None: False):
        rc = asyncio.run(
            cli_module.run_task(
                "m5 kernel bundle cli",
                model="deepseek/deepseek-chat",
                max_iterations=3,
                verbose=False,
                kernel_overrides=AgentKernelOverrides(llm_backend=_LlmTag("cli-ko")),
            )
        )
    assert rc == 0
    assert "OK cli-ko" in capsys.readouterr().out
