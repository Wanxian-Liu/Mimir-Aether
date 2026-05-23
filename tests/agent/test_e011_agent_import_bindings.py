"""E-011a: agent mixins bind model_metadata at import (ISSUES #9 follow-up)."""

from __future__ import annotations

import importlib

import pytest


@pytest.mark.parametrize(
    "module_name",
    [
        "agent.callers_mixin",
        "agent.core_loop",
    ],
)
def test_agent_mixin_imports_model_metadata(module_name: str) -> None:
    mod = importlib.import_module(module_name)
    assert hasattr(mod, "model_metadata")


def test_callers_mixin_model_metadata_callable() -> None:
    import agent.callers_mixin as cm

    assert hasattr(cm.model_metadata, "get_model_context_length")
    assert hasattr(cm.model_metadata, "estimate_messages_tokens_rough")
