"""Import smoke for gateway/agent mixin modules after GOD split (IR-20260520)."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

GATEWAY_MIXIN_MODULES = [
    "gateway._shared",
    "gateway.voice_mixin",
    "gateway.cron_mixin",
    "gateway.health_mixin",
    "gateway.session_mixin",
    "gateway.router_mixin",
    "gateway.agent_mixin",
    "gateway.command_handlers",
]

AGENT_MIXIN_MODULES = [
    "agent.config_mixin",
    "agent.callers_mixin",
    "agent.exec_mixin",
    "agent.recovery_mixin",
]


@pytest.mark.parametrize("module_name", GATEWAY_MIXIN_MODULES + AGENT_MIXIN_MODULES)
def test_mixin_module_imports(module_name: str) -> None:
    mod = importlib.import_module(module_name)
    assert mod is not None


def test_gateway_runner_imports() -> None:
    from gateway.run import GatewayRunner

    assert GatewayRunner.__name__ == "GatewayRunner"
