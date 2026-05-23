"""E-010: gateway mixins bind _shared helpers at module scope (ISSUES #9)."""

from __future__ import annotations

import importlib
from pathlib import Path
from types import ModuleType

import pytest


def _reload(module_name: str) -> ModuleType:
    importlib.invalidate_caches()
    return importlib.reload(importlib.import_module(module_name))


@pytest.mark.parametrize(
    "module_name,symbols",
    [
        (
            "gateway.router_mixin",
            (
                "_resolve_gateway_model",
                "_platform_config_key",
                "_load_gateway_config",
                "_resolve_runtime_agent_kwargs",
            ),
        ),
        (
            "gateway.command_handlers",
            (
                "_resolve_gateway_model",
                "_platform_config_key",
                "_load_gateway_config",
            ),
        ),
        (
            "gateway.agent_mixin",
            ("is_truthy_value", "_dequeue_pending_event"),
        ),
    ],
)
def test_mixin_module_binds_shared_symbols(module_name: str, symbols: tuple[str, ...]) -> None:
    mod = _reload(module_name)
    for sym in symbols:
        assert hasattr(mod, sym), f"{module_name} missing module-level {sym}"


def test_router_format_session_info_resolves_model(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from gateway.router_mixin import RouterMixin

    class _Runner(RouterMixin):
        pass

    monkeypatch.setattr("gateway.router_mixin._hermes_home", tmp_path)
    monkeypatch.setattr(
        "gateway.router_mixin._resolve_gateway_model",
        lambda config=None: "deepseek/deepseek-chat",
    )
    monkeypatch.setattr(
        "gateway.router_mixin._resolve_runtime_agent_kwargs",
        lambda: {"provider": "deepseek", "api_key": "k", "base_url": "http://127.0.0.1"},
    )
    monkeypatch.setattr(
        "agent.model_metadata.get_model_context_length",
        lambda *a, **k: 128000,
    )

    text = _Runner()._format_session_info()
    assert "deepseek/deepseek-chat" in text
