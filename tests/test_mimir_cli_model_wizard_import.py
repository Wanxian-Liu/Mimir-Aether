"""Import smoke for mimir_cli.model_wizard (P1-LONG-GOD C01)."""

from __future__ import annotations

import importlib
import inspect


def test_model_wizard_imports() -> None:
    mod = importlib.import_module("mimir_cli.model_wizard")
    assert hasattr(mod, "select_provider_and_model")


def test_cmd_model_delegates_to_wizard() -> None:
    import mimir_cli.main as main_mod

    src = inspect.getsource(main_mod.cmd_model)
    assert "select_provider_and_model" in src
    assert "model_wizard" in inspect.getsource(main_mod) or "select_provider_and_model" in src
