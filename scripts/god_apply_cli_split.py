#!/usr/bin/env python3
"""One-shot secondary split of mimir_cli/main.py (P1-LONG-GOD)."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "mimir_cli" / "main.py"

# (module_name, [(func_name, include_helpers_before)])
EXTRACT: list[tuple[str, list[str]]] = [
    (
        "session_picker",
        ["_relative_time", "_session_browse_picker", "_resolve_last_cli_session", "_resolve_session_by_name_or_id"],
    ),
    (
        "container_cli",
        ["_probe_container", "_exec_in_container"],
    ),
    (
        "model_wizard",
        [
            "select_provider_and_model",
            "_clear_stale_openai_base_url",
            "_prompt_provider_choice",
            "_model_flow_openrouter",
            "_model_flow_nous",
            "_model_flow_openai_codex",
            "_model_flow_qwen_oauth",
            "_model_flow_custom",
            "_auto_provider_name",
            "_save_custom_provider",
            "_remove_custom_provider",
            "_model_flow_named_custom",
            "_current_reasoning_effort",
            "_set_reasoning_effort",
            "_prompt_reasoning_effort_selection",
            "_model_flow_copilot",
            "_model_flow_copilot_acp",
            "_model_flow_kimi",
            "_model_flow_api_key_provider",
            "_run_anthropic_oauth_flow",
            "_model_flow_anthropic",
        ],
    ),
    (
        "update_command",
        [
            "_clear_bytecode_cache",
            "_gateway_prompt",
            "_build_web_ui",
            "_update_via_zip",
            "_stash_local_changes_if_needed",
            "_resolve_stash_selector",
            "_print_stash_cleanup_guidance",
            "_restore_stashed_changes",
            "_get_origin_url",
            "_is_fork",
            "_has_upstream_remote",
            "_add_upstream_remote",
            "_count_commits_between",
            "_should_skip_upstream_prompt",
            "_mark_skip_upstream_prompt",
            "_sync_fork_with_upstream",
            "_sync_with_upstream_if_needed",
            "_invalidate_update_cache",
            "_load_installable_optional_extras",
            "_install_python_dependencies_with_optional_fallback",
            "cmd_update",
        ],
    ),
    (
        "profile_command",
        ["cmd_profile", "_coalesce_session_name_args"],
    ),
]

COMMON_HEADER = '''\
"""Mimir CLI — {title} (P1-LONG-GOD extract from main.py)."""
from __future__ import annotations

import argparse
import json
import logging
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import time as _time
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent

logger = logging.getLogger(__name__)


'''


def _func_starts(lines: list[str]) -> dict[str, int]:
    starts: dict[str, int] = {}
    for i, line in enumerate(lines):
        if line.startswith("def ") or line.startswith("async def "):
            name = line.split("(")[0].split()[-1]
            starts[name] = i
    return starts


def _extract_block(lines: list[str], start: int, end: int) -> str:
    chunk = lines[start:end]
    while chunk and not chunk[-1].strip():
        chunk.pop()
    return "\n".join(chunk) + "\n\n"


def main() -> None:
    text = SRC.read_text(encoding="utf-8")
    lines = text.splitlines()
    starts = _func_starts(lines)
    sorted_starts = sorted(starts.items(), key=lambda x: x[1])
    name_to_end = {}
    for idx, (name, start) in enumerate(sorted_starts):
        name_to_end[name] = sorted_starts[idx + 1][1] if idx + 1 < len(sorted_starts) else len(lines)

    all_extracted: set[str] = set()
    for mod, funcs in EXTRACT:
        all_extracted.update(funcs)
        parts: list[str] = []
        for fn in funcs:
            if fn not in starts:
                raise SystemExit(f"{mod}: missing function {fn}")
            parts.append(_extract_block(lines, starts[fn], name_to_end[fn]))
        title = mod.replace("_", " ")
        body = COMMON_HEADER.format(title=title) + "".join(parts)
        (ROOT / "mimir_cli" / f"{mod}.py").write_text(body, encoding="utf-8")

    # Split main() for parser modules
    main_start = next(i for i, l in enumerate(lines) if l.startswith("def main():"))
    main_end = len(lines)
    main_body = lines[main_start + 1 : main_end]
    # dedent main body by 4 spaces
    dedented = []
    for line in main_body:
        if line.startswith("    "):
            dedented.append(line[4:])
        elif line.strip() == "":
            dedented.append("")
        else:
            dedented.append(line)

    parse_execute_idx = len(dedented)
    for i, line in enumerate(dedented):
        if line.strip().startswith("# Parse and execute"):
            parse_execute_idx = i
            break

    split_at = None
    for i, line in enumerate(dedented[:parse_execute_idx]):
        if "plugins command" in line:
            split_at = max(0, i - 2)
            break
    if split_at is None:
        split_at = parse_execute_idx // 2

    setup_body = dedented[:split_at]
    bind_body = dedented[split_at:parse_execute_idx]

    setup_header = '''\
"""Argparse subparser definitions — part 1 (P1-LONG-GOD)."""
from __future__ import annotations

import argparse
import logging
import sys

from mimir_cli import __version__, __release_date__
from mimir_cli.main_dispatch import get_command_handlers, _require_tty

logger = logging.getLogger(__name__)


def configure_parser_part1():
    """Build root parser, top-level flags, and first-half subcommands."""
    handlers = get_command_handlers()
'''

    bind_header = '''\
"""Argparse subparser definitions — part 2 (P1-LONG-GOD)."""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from mimir_cli.main_dispatch import get_command_handlers, _require_tty
from mimir_cli.paths import openclaw_migration_source_default

_OPENCLAW_MIGRATE_SOURCE_DEFAULT = str(openclaw_migration_source_default()).replace(
    str(Path.home()), "~", 1
)

logger = logging.getLogger(__name__)


def configure_parser_part2(parser, subparsers) -> None:
    """Register plugins through logs subcommands (second half)."""
    handlers = get_command_handlers()
'''

    setup_path = ROOT / "mimir_cli" / "cli_subparsers_setup.py"
    bind_path = ROOT / "mimir_cli" / "cli_subparsers_bind.py"

    setup_text = setup_header + "\n".join(f"    {l}" if l else "" for l in setup_body)
    # part1 must return parser, subparsers for main()
    if "return parser, subparsers" not in setup_text:
        setup_text = setup_text.rstrip() + "\n    return parser, subparsers\n"
    bind_text = bind_header + "\n".join(f"    {l}" if l else "" for l in bind_body)

    # Replace cmd_* references in setup with handlers.*
    for fn in sorted(all_extracted | {"main"}, reverse=False):
        pass
    handler_names = re.findall(r"set_defaults\(func=(\w+)\)", setup_text + bind_text)
    for h in set(handler_names):
        setup_text = setup_text.replace(f"func={h}", f"func=handlers['{h}']")
        bind_text = bind_text.replace(f"func={h}", f"func=handlers['{h}']")
    # fix double handlers for inline defs - revert cmd_skills etc that are defined inline
    for inline in (
        "cmd_skills", "cmd_plugins", "cmd_memory", "cmd_tools", "cmd_mcp",
        "cmd_sessions", "cmd_acp", "cmd_pairing", "cmd_insights", "cmd_claw",
    ):
        bind_text = bind_text.replace(f"func=handlers['{inline}']", f"func={inline}")
        setup_text = setup_text.replace(f"func=handlers['{inline}']", f"func={inline}")
    # setup part also uses handlers for set_defaults
    setup_text = setup_text.replace("handlers = get_command_handlers()\n", "handlers = get_command_handlers()\n", 1)

    setup_path.write_text(setup_text, encoding="utf-8")
    bind_path.write_text(bind_text, encoding="utf-8")

    # Rebuild main.py: keep module preamble through logger, then non-extracted functions.
    logger_line = next(i for i, l in enumerate(lines) if l.strip() == "logger = logging.getLogger(__name__)")
    preamble = "\n".join(lines[: logger_line + 1]) + "\n\n"

    imports_block = '''\
from mimir_cli.model_wizard import select_provider_and_model
from mimir_cli.session_picker import (
    _session_browse_picker,
    _resolve_last_cli_session,
    _resolve_session_by_name_or_id,
)
from mimir_cli.container_cli import _probe_container, _exec_in_container
from mimir_cli.update_command import cmd_update
from mimir_cli.profile_command import cmd_profile, _coalesce_session_name_args
from mimir_cli.cli_subparsers_setup import configure_parser_part1
from mimir_cli.cli_subparsers_bind import configure_parser_part2

'''

    # Keep functions not extracted
    keep_funcs = []
    for name, start in sorted_starts:
        if name in all_extracted or name == "main":
            continue
        keep_funcs.append(_extract_block(lines, start, name_to_end[name]))

    thin_main = '''\
def main():
    """Main entry point for mimir CLI."""
    parser, subparsers = configure_parser_part1()
    configure_parser_part2(parser, subparsers)

    from mimir_cli.config import get_container_exec_info

    container_info = get_container_exec_info()
    if container_info:
        _exec_in_container(container_info, sys.argv[1:])
        sys.exit(1)

    _processed_argv = _coalesce_session_name_args(sys.argv[1:])
    args = parser.parse_args(_processed_argv)

    if getattr(args, "version", False):
        cmd_version(args)
        return

    if (getattr(args, "resume", None) or getattr(args, "continue_last", None)) and args.command is None:
        args.command = "chat"
        args.query = None
        args.model = None
        args.provider = None
        args.toolsets = None
        args.verbose = False
        if not hasattr(args, "worktree"):
            args.worktree = False
        cmd_chat(args)
        return

    if args.command is None:
        args.query = None
        args.model = None
        args.provider = None
        args.toolsets = None
        args.verbose = False
        args.resume = None
        args.continue_last = None
        if not hasattr(args, "worktree"):
            args.worktree = False
        cmd_chat(args)
        return

    if hasattr(args, "func"):
        args.func(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
'''

    # Insert imports after logger = line in preamble
    if "from mimir_cli.model_wizard import" not in preamble:
        preamble = preamble.replace(
            "logger = logging.getLogger(__name__)\n\n",
            "logger = logging.getLogger(__name__)\n\n" + imports_block,
        )

    new_main = preamble + "".join(keep_funcs) + thin_main
    SRC.write_text(new_main, encoding="utf-8")

  # main_dispatch module
    dispatch = '''\
"""Command handler registry for argparse (avoids circular imports in parser modules)."""
from __future__ import annotations

import sys


def _require_tty(command_name: str) -> None:
    if not sys.stdin.isatty():
        print(
            f"Error: 'mimir {command_name}' requires an interactive terminal.\\n"
            f"It cannot be run through a pipe or non-interactive subprocess.\\n"
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
'''
    (ROOT / "mimir_cli" / "main_dispatch.py").write_text(dispatch, encoding="utf-8")

    print(f"main.py now {len(new_main.splitlines())} lines")
    print("Wrote model_wizard, session_picker, container_cli, update_command, profile_command")
    print("Wrote cli_subparsers_setup.py, cli_subparsers_bind.py, main_dispatch.py")


if __name__ == "__main__":
    main()
