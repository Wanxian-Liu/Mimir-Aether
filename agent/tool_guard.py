"""
Tool Guard — Structured Permissions + Poka-Yoke Validators.

Phase XIV: Absorbed from Anthropic "Building Effective Agents" (Poka-Yoke)
and deusyu Harness Engineering (熵管理 #6 → structured permissions).

Architecture:
  1. classify_risk() — maps every tool to a ToolRisk tier
  2. poka_yoke_validate() — catches common LLM mistakes before dispatch
  3. guard_tool_call() — orchestrator called by strategy.pre_validate_tool_call()

Risk tiers (Anthropic "Beyond Permission Prompts"):
  READ_ONLY   — zero side effects, auto-approved
  FILE_WRITE  — filesystem mutation, warn on relative paths
  NETWORK     — external requests, rate-limit consideration
  SYSTEM      — shell / subprocess / delegation
  DESTRUCTIVE — irreversible, should require confirmation
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)


# ── Risk Tiers ──────────────────────────────────────────────────────────────

class ToolRisk(Enum):
    """Tool risk classification for structured permissions."""
    READ_ONLY = "read_only"       # 零副作用：读文件、搜索、查看
    FILE_WRITE = "file_write"     # 文件系统写入
    NETWORK = "network"           # 外部网络请求
    SYSTEM = "system"             # shell / 子进程 / 委托
    DESTRUCTIVE = "destructive"   # 不可逆操作（训练、删除等）


# Map tool_name → ToolRisk.  Prefix patterns (ending in _) match families.
_RISK_MAP: list[tuple[str, ToolRisk]] = [
    # ── READ_ONLY ──
    ("read_file",              ToolRisk.READ_ONLY),
    ("search_files",           ToolRisk.READ_ONLY),
    ("session_search",         ToolRisk.READ_ONLY),
    ("skill_view",             ToolRisk.READ_ONLY),
    ("skills_list",            ToolRisk.READ_ONLY),
    ("list_capsules",          ToolRisk.READ_ONLY),
    ("get_capsule_by_id",     ToolRisk.READ_ONLY),
    ("get_env",                ToolRisk.READ_ONLY),
    ("clarify",                ToolRisk.READ_ONLY),
    ("todo",                   ToolRisk.READ_ONLY),
    ("text_to_speech",         ToolRisk.READ_ONLY),
    ("set_strategy",           ToolRisk.READ_ONLY),
    # RL read-only
    ("rl_check_status",        ToolRisk.READ_ONLY),
    ("rl_get_current_config",  ToolRisk.READ_ONLY),
    ("rl_get_results",         ToolRisk.READ_ONLY),
    ("rl_list_environments",   ToolRisk.READ_ONLY),
    ("rl_list_runs",           ToolRisk.READ_ONLY),
    # OpenClaw native (prefix match)
    ("browser_snapshot",       ToolRisk.READ_ONLY),
    ("browser_console",        ToolRisk.READ_ONLY),
    ("browser_get_images",     ToolRisk.READ_ONLY),

    # ── FILE_WRITE ──
    ("write_file",             ToolRisk.FILE_WRITE),
    ("patch",                  ToolRisk.FILE_WRITE),
    ("memory",                 ToolRisk.FILE_WRITE),
    ("skill_manage",           ToolRisk.FILE_WRITE),
    ("improve_capsule",        ToolRisk.FILE_WRITE),
    ("produce_capsule",        ToolRisk.FILE_WRITE),

    # ── NETWORK ──
    ("web_search",             ToolRisk.NETWORK),
    ("web_extract",            ToolRisk.NETWORK),
    ("send_message",           ToolRisk.NETWORK),
    ("ha_",                    ToolRisk.NETWORK),   # prefix: ha_call_service etc.
    ("browser_navigate",       ToolRisk.NETWORK),
    ("browser_click",          ToolRisk.NETWORK),
    ("browser_type",           ToolRisk.NETWORK),
    ("browser_back",           ToolRisk.NETWORK),
    ("browser_scroll",         ToolRisk.NETWORK),
    ("browser_press",          ToolRisk.NETWORK),
    ("browser_vision",         ToolRisk.NETWORK),
    ("vision_analyze",         ToolRisk.NETWORK),

    # ── SYSTEM ──
    ("terminal",               ToolRisk.SYSTEM),
    ("execute_code",           ToolRisk.SYSTEM),
    ("process",                ToolRisk.SYSTEM),
    ("delegate_task",          ToolRisk.SYSTEM),
    ("cronjob",                ToolRisk.SYSTEM),

    # ── DESTRUCTIVE ──
    ("rl_start_training",      ToolRisk.DESTRUCTIVE),
    ("rl_stop_training",       ToolRisk.DESTRUCTIVE),
    ("rl_edit_config",         ToolRisk.DESTRUCTIVE),
    ("rl_select_environment",  ToolRisk.DESTRUCTIVE),
    ("rl_test_inference",      ToolRisk.DESTRUCTIVE),
]


def classify_risk(tool_name: str) -> ToolRisk:
    """Return the risk tier for a tool.  Default: SYSTEM (conservative)."""
    for prefix, risk in _RISK_MAP:
        if prefix.endswith("_"):
            if tool_name.startswith(prefix):
                return risk
        elif tool_name == prefix:
            return risk
    return ToolRisk.SYSTEM  # unknown tools → conservative


# ── Poka-Yoke Validators ────────────────────────────────────────────────────

# File-path parameter names (for relative-path detection).
_PATH_PARAM_NAMES: set[str] = {
    "path", "file_path", "source", "destination", "target",
    "workdir", "output", "input", "db_path", "dst", "src",
}


def _guard_base_dir() -> str:
    """Absolute base for path containment checks (aligned with tools.builtin._ALLOWED_BASE_DIR)."""
    return os.path.abspath(os.path.expanduser(os.environ.get("MIMIR_BASE_DIR", "~")))


def resolve_path_for_guard(path_str: str, base_dir: str | None = None) -> str:
    """Resolve a path argument to absolute for guard checks.

    Relative paths resolve against ``base_dir`` or the process cwd — matching
    ``os.path.abspath`` / ``tools.builtin._safe_path`` behaviour so guard checks
    do not compare unresolved relative paths.
    """
    raw = path_str.strip()
    if not raw:
        return raw
    expanded = os.path.expanduser(raw)
    if os.path.isabs(expanded):
        return os.path.normpath(expanded)
    root = base_dir or os.getcwd()
    return os.path.normpath(os.path.join(root, expanded))


def _is_relative_path_arg(value: str) -> bool:
    raw = value.strip()
    if not raw:
        return False
    if raw.startswith(("/", "~")):
        return False
    if raw.startswith("$") or raw.startswith("{"):
        return False
    return True


def _path_stays_under_allowed(resolved: str) -> bool:
    allowed = _guard_base_dir()
    try:
        resolved_real = os.path.realpath(resolved)
        allowed_real = os.path.realpath(allowed)
    except (OSError, ValueError):
        return False
    return (
        resolved_real == allowed_real
        or resolved_real.startswith(allowed_real + os.sep)
    )


def _validate_file_paths(tool_name: str, args: dict) -> tuple[list[str], str]:
    """Poka-yoke: resolve path args; warn on relative; block escape outside base."""
    risk = classify_risk(tool_name)
    if risk not in (ToolRisk.FILE_WRITE, ToolRisk.DESTRUCTIVE):
        return [], ""

    warnings: list[str] = []
    cwd = os.getcwd()
    allowed_base = _guard_base_dir()

    for key, value in (args or {}).items():
        if key not in _PATH_PARAM_NAMES:
            continue
        if not isinstance(value, str) or not value.strip():
            continue
        if value.startswith("$") or value.startswith("{"):
            continue

        resolved = resolve_path_for_guard(value, cwd)

        if _is_relative_path_arg(value):
            warnings.append(
                f"Tool '{tool_name}' received relative path '{key}={value}'. "
                f"Resolved to '{resolved}'. Use an absolute path to avoid ambiguity."
            )

        if not _path_stays_under_allowed(resolved):
            block = (
                f"Path argument '{key}' resolves outside allowed base "
                f"({allowed_base}): '{value}' → '{resolved}'. "
                f"Tool '{tool_name}' blocked by ToolGuard."
            )
            return warnings, block

    return warnings, ""


# Shell-injection patterns that should never appear in a terminal command.
_DANGEROUS_SHELL_PATTERNS: list[tuple[str, str]] = [
    ("rm -rf /",       "recursive root deletion"),
    ("sudo rm",        "privileged deletion"),
    ("mkfs.",          "filesystem format"),
    ("> /dev/sda",     "raw device overwrite"),
    ("dd if=",         "raw device copy (may overwrite)"),
    (":(){ :|:& };:",  "fork bomb"),
    ("chmod 777 /",    "world-writable root"),
    ("curl ... | sh",  "pipe-to-shell (supply-chain risk)"),
    ("wget ... | sh",  "pipe-to-shell (supply-chain risk)"),
]


def _validate_dangerous_shell(tool_name: str, args: dict) -> list[str]:
    """Poka-yoke: detect obviously-dangerous shell patterns."""
    if tool_name != "terminal":
        return []

    command = (args or {}).get("command", "")
    if not isinstance(command, str) or not command.strip():
        return []

    warnings: list[str] = []
    cmd_lower = command.lower()
    for pattern, description in _DANGEROUS_SHELL_PATTERNS:
        if pattern in cmd_lower:
            warnings.append(
                f"Tool 'terminal' command matches dangerous pattern "
                f"'{pattern}' ({description}). "
                f"Verify this is intentional before executing."
            )

    return warnings


# ── Orchestrator ────────────────────────────────────────────────────────────

@dataclass
class GuardResult:
    """Result of tool-guard validation."""
    ok: bool
    risk: ToolRisk = ToolRisk.SYSTEM
    warnings: list[str] = field(default_factory=list)
    block_reason: str = ""


def guard_tool_call(tool_name: str, args: dict) -> GuardResult:
    """Run all poka-yoke validators on a tool call.

    Called by strategy.pre_validate_tool_call() before dispatch.
    Returns GuardResult — ok=False means the call should be blocked.
    """
    risk = classify_risk(tool_name)
    warnings: list[str] = []

    # 1. Path resolution + relative-path warn + traversal block (FILE_WRITE tools)
    path_warnings, block_reason = _validate_file_paths(tool_name, args)
    warnings.extend(path_warnings)

    # 2. Dangerous shell patterns (terminal tool)
    warnings.extend(_validate_dangerous_shell(tool_name, args))

    if warnings:
        for w in warnings:
            logger.warning("ToolGuard [%s] risk=%s: %s", tool_name, risk.value, w)

    if block_reason:
        return GuardResult(
            ok=False, risk=risk, warnings=warnings, block_reason=block_reason
        )

    return GuardResult(ok=True, risk=risk, warnings=warnings)
