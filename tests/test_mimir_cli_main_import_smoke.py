"""P1-GOD-00: mimir_cli.main import smoke — delegation intact before GOD split."""

from __future__ import annotations

import importlib
import inspect


def test_mimir_cli_main_imports() -> None:
    mod = importlib.import_module("mimir_cli.main")
    assert hasattr(mod, "main")
    assert callable(mod.main)


def test_cmd_chat_delegates_to_chat_runner() -> None:
    from mimir_cli import main as mimir_main

    src = inspect.getsource(mimir_main.cmd_chat)
    assert "chat_runner" in src
    assert "cli.main" not in src


def test_cmd_gateway_delegates() -> None:
    from mimir_cli import main as mimir_main

    src = inspect.getsource(mimir_main.cmd_gateway)
    assert "gateway_command" in src


def test_main_module_reloads_without_nameerror() -> None:
    importlib.invalidate_caches()
    mod = importlib.reload(importlib.import_module("mimir_cli.main"))
    assert hasattr(mod, "cmd_chat")
    assert hasattr(mod, "main")
