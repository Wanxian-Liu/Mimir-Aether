"""E-008 D7-3 — gateway / config / chat CLI smoke tests."""

from __future__ import annotations

import inspect
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


def test_gateway_module_exports_command():
    from mimir_cli.gateway import gateway_command

    assert callable(gateway_command)


def test_config_module_loads_cli_config():
    from mimir_cli.config import CLI_CONFIG, load_config

    assert isinstance(CLI_CONFIG, dict)
    assert "clarify" in CLI_CONFIG
    cfg = load_config()
    assert cfg is None or isinstance(cfg, dict)


def test_cmd_gateway_delegates_to_gateway_command():
    from mimir_cli import main as mimir_main

    src = inspect.getsource(mimir_main.cmd_gateway)
    assert "gateway_command" in src


def test_cmd_config_delegates_to_config_command():
    from mimir_cli import main as mimir_main

    src = inspect.getsource(mimir_main.cmd_config)
    assert "config_command" in src


def test_cmd_chat_uses_chat_runner():
    from mimir_cli import main as mimir_main

    src = inspect.getsource(mimir_main.cmd_chat)
    assert "chat_runner" in src
    assert "cli.main" not in src


def test_cli_py_is_thin_shim():
    cli_path = ROOT / "cli.py"
    lines = [ln for ln in cli_path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert len(lines) <= 20, f"cli.py should be a shim, got {len(lines)} non-empty lines"


def test_no_dangling_cli_part_files():
    for name in ("cli_part1.py", "cli_part3.py", "cli_cron.py"):
        assert not (ROOT / name).exists(), f"orphan {name} should be removed"


def test_python_cli_py_help_exits_zero():
    proc = subprocess.run(
        [sys.executable, str(ROOT / "cli.py"), "--help"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert proc.returncode == 0
    assert "mimir" in proc.stdout.lower() or "MimirAether" in proc.stdout
