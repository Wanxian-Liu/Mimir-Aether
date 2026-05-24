#!/usr/bin/env python3
"""One-shot secondary split of gateway/router_mixin.py into gateway/router/* mixins."""

from __future__ import annotations

import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "gateway" / "router_mixin.py"
OUT_DIR = ROOT / "gateway" / "router"

# (filename_stem, class_name, method_names, extra_class_lines)
SLICES: list[tuple[str, str, list[str], list[str]]] = [
    (
        "inbound_prep_mixin",
        "InboundPrepMixin",
        ["_prepare_inbound_message_text"],
        [],
    ),
    (
        "core_route_mixin",
        "CoreRouteMixin",
        ["_handle_message"],
        [],
    ),
    (
        "agent_route_mixin",
        "AgentRouteMixin",
        ["_handle_message_with_agent", "_format_session_info"],
        [],
    ),
    (
        "session_commands_mixin",
        "SessionCommandsMixin",
        [
            "_handle_reset_command",
            "_handle_profile_command",
            "_handle_status_command",
            "_handle_stop_command",
            "_handle_restart_command",
            "_handle_help_command",
            "_handle_commands_command",
        ],
        [],
    ),
    (
        "model_commands_mixin",
        "ModelCommandsMixin",
        [
            "_handle_model_command",
            "_handle_provider_command",
            "_handle_personality_command",
            "_handle_retry_command",
            "_handle_undo_command",
            "_handle_set_home_command",
        ],
        [],
    ),
    (
        "media_mixin",
        "MediaMixin",
        ["_get_guild_id", "_deliver_media_from_response"],
        [],
    ),
    (
        "tuning_commands_mixin",
        "TuningCommandsMixin",
        [
            "_handle_rollback_command",
            "_handle_reasoning_command",
            "_handle_fast_command",
            "_handle_yolo_command",
            "_handle_verbose_command",
            "_handle_compress_command",
            "_handle_title_command",
            "_handle_resume_command",
            "_handle_branch_command",
            "_handle_usage_command",
            "_handle_insights_command",
            "_handle_reload_mcp_command",
        ],
        [],
    ),
    (
        "admin_commands_mixin",
        "AdminCommandsMixin",
        [
            "_handle_approve_command",
            "_handle_deny_command",
            "_handle_debug_command",
            "_handle_update_command",
        ],
        [
            "    _APPROVAL_TIMEOUT_SECONDS = 300  # 5 minutes",
            "",
            "    _UPDATE_ALLOWED_PLATFORMS = frozenset({",
            "        Platform.TELEGRAM, Platform.DISCORD, Platform.SLACK, Platform.WHATSAPP,",
            "        Platform.SIGNAL, Platform.MATTERMOST, Platform.MATRIX,",
            "        Platform.HOMEASSISTANT, Platform.EMAIL, Platform.SMS, Platform.DINGTALK,",
            "        Platform.FEISHU, Platform.WECOM, Platform.WECOM_CALLBACK, Platform.WEIXIN, Platform.BLUEBUBBLES, Platform.LOCAL,",
            "    })",
        ],
    ),
]

HEADER = '''\
"""Gateway router {desc} — extracted from router_mixin (P1-LONG-GOD)."""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import shlex
import subprocess
import time
import uuid as _uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from gateway._shared import (
    _check_unavailable_skill,
    _format_gateway_process_notification,
    _load_gateway_config,
    _platform_config_key,
    _resolve_gateway_model,
    _resolve_runtime_agent_kwargs,
    _resolve_hermes_bin,
)
from gateway.home_paths import _hermes_home
from gateway.platforms.base import MessageEvent, MessageType, Platform, merge_pending_message_event
from gateway.restart import _AGENT_PENDING_SENTINEL
from gateway.session import SessionSource, build_session_context, build_session_context_prompt
from utils import atomic_yaml_write

logger = logging.getLogger(__name__)


'''


def _method_starts(lines: list[str]) -> dict[str, int]:
    starts: dict[str, int] = {}
    for i, line in enumerate(lines):
        if line.startswith("    async def ") or line.startswith("    def "):
            name = line.split("(")[0].split()[-1]
            starts[name] = i
        elif line.startswith("    _") and " = " in line and not line.strip().startswith("def "):
            # class attrs like _APPROVAL_TIMEOUT_SECONDS
            name = line.split("=")[0].strip().split()[-1]
            if name.startswith("_"):
                starts[name] = i
    return starts


def _extract_method(lines: list[str], start: int, end: int) -> str:
    chunk = lines[start:end]
    # drop trailing blank lines
    while chunk and not chunk[-1].strip():
        chunk.pop()
    return "\n".join(chunk) + "\n"


def main() -> None:
    text = SRC.read_text(encoding="utf-8")
    lines = text.splitlines()
    starts = _method_starts(lines)
    ordered_names = [n for n in starts if n in {m for _, _, ms, _ in SLICES for m in ms}]

    # compute end lines
    sorted_starts = sorted(starts.items(), key=lambda x: x[1])
    name_to_end: dict[str, int] = {}
    for idx, (name, start) in enumerate(sorted_starts):
        if idx + 1 < len(sorted_starts):
            name_to_end[name] = sorted_starts[idx + 1][1]
        else:
            name_to_end[name] = len(lines)

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    mixin_classes: list[tuple[str, str]] = []
    for stem, class_name, methods, extra_lines in SLICES:
        body_parts: list[str] = []
        for extra in extra_lines:
            body_parts.append(extra)
        for method in methods:
            if method not in starts:
                raise SystemExit(f"missing method {method}")
            body_parts.append(_extract_method(lines, starts[method], name_to_end[method]))

        desc = stem.replace("_", " ")
        content = HEADER.format(desc=desc)
        content += f"class {class_name}:\n"
        content += f'    """Router {desc} mixin for GatewayRunner."""\n\n'
        content += "\n".join(body_parts)
        if not content.endswith("\n"):
            content += "\n"
        (OUT_DIR / f"{stem}.py").write_text(content, encoding="utf-8")
        mixin_classes.append((stem, class_name))

    init_lines = ['"""Gateway router sub-mixins (P1-LONG-GOD secondary split)."""\n']
    for stem, class_name in mixin_classes:
        init_lines.append(f"from gateway.router.{stem} import {class_name}")
    (OUT_DIR / "__init__.py").write_text("\n".join(init_lines) + "\n", encoding="utf-8")

    # Fix agent_route _config_path -> _hermes_home path
    agent_path = OUT_DIR / "agent_route_mixin.py"
    agent_text = agent_path.read_text(encoding="utf-8")
    agent_text = agent_text.replace(
        "with open(_config_path, encoding=\"utf-8\") as _pf:",
        "with open(_hermes_home / \"config.yaml\", encoding=\"utf-8\") as _pf:",
    )
    agent_path.write_text(agent_text, encoding="utf-8")

    imports = "\n".join(
        f"from gateway.router.{stem} import {cls}" for stem, cls in mixin_classes
    )
    mro = ", ".join(cls for _, cls in reversed(mixin_classes))
    router_mixin_new = f'''\
"""
RouterMixin — message routing, command handling, media delivery.

Secondary split (P1-LONG-GOD): composition of gateway/router/* mixins.
"""
from __future__ import annotations

{imports}


class RouterMixin({mro}):
    """Message routing: inbound processing, command dispatch, media delivery.

    Designed to be mixed into GatewayRunner.
    """
'''
    SRC.write_text(router_mixin_new, encoding="utf-8")
    print(f"Wrote {len(mixin_classes)} mixins under {OUT_DIR}")
    print(f"router_mixin.py now {len(router_mixin_new.splitlines())} lines")


if __name__ == "__main__":
    main()
