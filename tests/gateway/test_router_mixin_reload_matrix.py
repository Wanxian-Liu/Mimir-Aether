"""P1-GOD-00: RouterMixin symbol matrix — reload without NameError after secondary split."""

from __future__ import annotations

import importlib
import importlib.util
from types import ModuleType

import pytest

from gateway.router_mixin import RouterMixin

# Core routing pipeline (must survive gateway/router/* extractions)
ROUTER_MIXIN_SYMBOLS = (
    "_handle_message",
    "_prepare_inbound_message_text",
    "_handle_message_with_agent",
    "_format_session_info",
    "_handle_reset_command",
    "_handle_model_command",
    "_deliver_media_from_response",
    "_handle_approve_command",
    "_handle_update_command",
)


def _reload(module_name: str) -> ModuleType:
    importlib.invalidate_caches()
    return importlib.reload(importlib.import_module(module_name))


@pytest.mark.parametrize("symbol", ROUTER_MIXIN_SYMBOLS)
def test_router_mixin_exposes_routing_symbols(symbol: str) -> None:
    assert hasattr(RouterMixin, symbol), f"RouterMixin missing {symbol}"


def test_router_mixin_module_reloads_without_nameerror() -> None:
    mod = _reload("gateway.router_mixin")
    assert hasattr(mod, "RouterMixin")
    for sym in ROUTER_MIXIN_SYMBOLS:
        assert hasattr(mod.RouterMixin, sym), f"reloaded RouterMixin missing {sym}"


def test_router_subpackage_imports_when_present() -> None:
    """gateway/router/* mixins — skip until G01+ lands."""
    if importlib.util.find_spec("gateway.router.inbound_prep_mixin") is None:
        pytest.skip("gateway.router package not created yet")
    import gateway.router.inbound_prep_mixin  # noqa: F401
