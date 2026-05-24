"""Command handler registry for argparse (avoids circular imports in parser modules)."""
from __future__ import annotations

import sys


def _require_tty(command_name: str) -> None:
    if not sys.stdin.isatty():
        print(
            f"Error: 'mimir {command_name}' requires an interactive terminal.\n"
            f"It cannot be run through a pipe or non-interactive subprocess.\n"
            f"Run it directly in your terminal instead.",
            file=sys.stderr,
        )
        sys.exit(1)


def get_command_handlers():
    from mimir_cli import main as main_mod

    names = [
        "cmd_chat", "cmd_model", "cmd_gateway", "cmd_setup", "cmd_whatsapp",
        "cmd_login", "cmd_logout", "cmd_auth", "cmd_status", "cmd_cron",
        "cmd_webhook", "cmd_doctor", "cmd_dump", "cmd_debug", "cmd_backup",
        "cmd_import", "cmd_config",
        "cmd_version", "cmd_update", "cmd_uninstall", "cmd_profile",
        "cmd_completion", "cmd_dashboard", "cmd_logs",
    ]
    return {n: getattr(main_mod, n) for n in names}
