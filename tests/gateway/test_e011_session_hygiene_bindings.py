"""E-011a: gateway session-hygiene path can import model_metadata helpers."""

from __future__ import annotations

import importlib
from types import ModuleType

import pytest


def _reload(module_name: str) -> ModuleType:
    importlib.invalidate_caches()
    return importlib.reload(importlib.import_module(module_name))


def test_router_mixin_session_hygiene_imports_model_metadata() -> None:
    """Session hygiene block imports estimate/get_context from agent.model_metadata."""
    from agent.model_metadata import (
        estimate_messages_tokens_rough,
        get_model_context_length,
    )

    history = [
        {"role": "user", "content": "hello"},
        {"role": "assistant", "content": "hi"},
        {"role": "user", "content": "status"},
        {"role": "assistant", "content": "ok"},
    ]
    tokens = estimate_messages_tokens_rough(history)
    assert tokens > 0
    ctx = get_model_context_length("deepseek/deepseek-chat")
    assert ctx >= 8000


def test_router_mixin_reloads_without_nameerror() -> None:
    mod = _reload("gateway.router_mixin")
    for sym in (
        "_load_gateway_config",
        "_resolve_gateway_model",
        "_platform_config_key",
    ):
        assert hasattr(mod, sym), f"gateway.router_mixin missing {sym}"
