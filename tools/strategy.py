"""
Strategy Tool Module Ã¢ÂÂ Behavioral Strategy Pattern

Provides a pluggable strategy framework for the agent: different execution
strategies (concise, thorough, creative, etc.) can be selected at runtime
and influence how the agent approaches tasks.

Design:
- ``Strategy`` base class defines the interface
- Concrete strategies implement specific behaviors
- ``StrategyContext`` holds the current strategy and delegates to it
- ``set_strategy`` tool allows switching strategies mid-session

Tool Dispatch Strategy Layer (pre-validation + routing):
- ``pre_validate_tool_call()`` Ã¢ÂÂ parameter size & path safety checks before dispatch
- ``route_tool_call()`` Ã¢ÂÂ tool name remapping & capability gating
- Integrated via ``model_tools.handle_function_call()``
"""

import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from tools.registry import registry, tool_error, tool_result

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Strategy Base & Built-in Strategies
# ---------------------------------------------------------------------------


class Strategy:
    """Base class for agent behavior strategies."""

    name: str = "base"
    description: str = "Base strategy"

    def apply(self, context: dict) -> dict:
        """Apply the strategy to the given context.

        Returns a dict with strategy-specific instructions or modifiers.
        """
        return {}

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
        }


class ConciseStrategy(Strategy):
    """Favor short, direct responses with minimal exposition."""

    name = "concise"
    description = "Short, direct responses Ã¢ÂÂ prefer brevity over detail"


class ThoroughStrategy(Strategy):
    """Provide detailed explanations and comprehensive coverage."""

    name = "thorough"
    description = "Detailed, comprehensive responses Ã¢ÂÂ leave no stone unturned"


class CreativeStrategy(Strategy):
    """Encourage creative, lateral thinking and novel approaches."""

    name = "creative"
    description = "Creative, lateral thinking Ã¢ÂÂ explore novel angles and ideas"


class AnalyticalStrategy(Strategy):
    """Systematic, logical analysis with structured reasoning."""

    name = "analytical"
    description = "Systematic, logical analysis Ã¢ÂÂ break down problems step by step"


# ---------------------------------------------------------------------------
# Strategy Registry
# ---------------------------------------------------------------------------

_BUILTIN_STRATEGIES: dict[str, Strategy] = {
    "concise": ConciseStrategy(),
    "thorough": ThoroughStrategy(),
    "creative": CreativeStrategy(),
    "analytical": AnalyticalStrategy(),
}

_current_strategy: Strategy = _BUILTIN_STRATEGIES["thorough"]


def get_strategy(name: str | None = None) -> Strategy:
    """Get a strategy by name, or the current active strategy."""
    if name is not None:
        return _BUILTIN_STRATEGIES.get(name, _current_strategy)
    return _current_strategy


def set_strategy(name: str) -> Strategy:
    """Set the current strategy by name. Falls back to 'thorough' if unknown."""
    global _current_strategy
    _current_strategy = _BUILTIN_STRATEGIES.get(name, _BUILTIN_STRATEGIES["thorough"])
    logger.info("Strategy changed to: %s", _current_strategy.name)
    return _current_strategy


def list_strategies() -> list[dict]:
    """Return all registered strategies as dicts."""
    return [s.to_dict() for s in _BUILTIN_STRATEGIES.values()]


# ---------------------------------------------------------------------------
# Tool Schema & Handler
# ---------------------------------------------------------------------------

SET_STRATEGY_SCHEMA = {
    "name": "set_strategy",
    "description": (
        "Set the agent's behavioral strategy. Available strategies: "
        + ", ".join(f"'{name}'" for name in _BUILTIN_STRATEGIES)
        + ". Use 'list' action to see all available strategies with descriptions."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["set", "get", "list"],
                "description": "Action: 'set' a strategy, 'get' the current one, or 'list' all available."
            },
            "name": {
                "type": "string",
                "description": "Strategy name (required for 'set' action). One of: "
                + ", ".join(_BUILTIN_STRATEGIES),
            },
        },
        "required": ["action"],
    },
}


def set_strategy_tool(args: dict, **kw) -> str:
    """Handle set_strategy tool calls."""
    action = args.get("action", "get")

    if action == "list":
        strategies = list_strategies()
        current = _current_strategy.name
        return tool_result({
            "strategies": strategies,
            "current": current,
        })

    if action == "get":
        return tool_result({
            "current": _current_strategy.name,
            "description": _current_strategy.description,
        })

    if action == "set":
        name = args.get("name", "").strip().lower()
        if not name:
            return tool_error("'name' is required when action='set'")
        if name not in _BUILTIN_STRATEGIES:
            avail = ", ".join(_BUILTIN_STRATEGIES)
            return tool_error(f"Unknown strategy '{name}'. Available: {avail}")
        new_strategy = set_strategy(name)
        return tool_result({
            "previous": _current_strategy.name if new_strategy != _current_strategy else name,
            "current": new_strategy.name,
            "description": new_strategy.description,
        })

    return tool_error(f"Unknown action: {action}")


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

registry.register(
    name="set_strategy",
    toolset="core",
    schema=SET_STRATEGY_SCHEMA,
    handler=set_strategy_tool,
    description="Set or query the agent's behavioral strategy",
    emoji="Ã°ÂÂÂ¯",
)


# ============================================================================
# Tool Dispatch Strategy Layer Ã¢ÂÂ Pre-validation & Routing
# ============================================================================
#
# These functions are called by model_tools.handle_function_call() BEFORE
# coercion and registry dispatch.  They form a lightweight middleware that:
#
#   1. Pre-validates Ã¢ÂÂ catches obviously-bad arguments early
#      (oversized params, path traversal, etc.)
#   2. Routes Ã¢ÂÂ remaps deprecated tool names, gates disabled tools
#
# Both layers are designed to fail-open: unknown tools / edge cases pass
# through to the registry, which has its own error handling.


# ---------------------------------------------------------------------------
# Pre-validation: parameter size limits
# ---------------------------------------------------------------------------

# Parameter names that typically carry large payloads.
# Keys: parameter name Ã¢ÂÂ max characters (or True to use default).
_PARAM_SIZE_LIMITS: dict[str, int] = {
    "content": 500_000,      # write_file content
    "code": 500_000,         # execute_code / patch content
    "command": 32_768,       # terminal command (32KB Ã¢ÂÂ OS arg limit)
    "input_text": 100_000,   # produce_capsule input
}

# Default max size for any single string argument (1 MB).
_DEFAULT_MAX_PARAM_SIZE: int = 1_048_576

# Parameter names that should NEVER be capped (they carry references, not data).
_SIZE_CHECK_SKIP_PARAMS: set[str] = {"path", "file_path", "capsule_id", "session_id"}


def _check_param_size(tool_name: str, args: dict) -> Optional[str]:
    """Check tool arguments for oversized values.

    Returns an error string if any argument exceeds its limit, or None if all pass.
    """
    if not args or not isinstance(args, dict):
        return None

    for key, value in args.items():
        if not isinstance(value, str):
            continue
        if key in _SIZE_CHECK_SKIP_PARAMS:
            continue

        limit = _PARAM_SIZE_LIMITS.get(key, _DEFAULT_MAX_PARAM_SIZE)
        size = len(value)
        if size > limit:
            return (
                f"Argument '{key}' is too large ({size:,} chars, limit {limit:,}). "
                f"Tool '{tool_name}' rejected in pre-validation."
            )

    return None


# ---------------------------------------------------------------------------
# Pre-validation: path safety
# ---------------------------------------------------------------------------

# Parameter names known to carry file paths (checked for traversal attacks).
_PATH_PARAM_NAMES: set[str] = {
    "path", "file_path", "source", "destination", "target",
    "workdir", "output", "input", "dst", "src",
}

# Paths that are always allowed (system temp, etc.).
_ALWAYS_ALLOWED_PREFIXES: tuple[str, ...] = (
    "/tmp/",
    "/dev/null",
    "/dev/stdout",
    "/dev/stderr",
    "/dev/stdin",
)


def _check_path_safety(tool_name: str, args: dict) -> Optional[str]:
    """Check file-path arguments for traversal / injection patterns.

    Returns an error string if a path looks malicious, or None if all pass.
    """
    if not args or not isinstance(args, dict):
        return None

    for key, value in args.items():
        if not isinstance(value, str):
            continue
        if key not in _PATH_PARAM_NAMES:
            continue

        path_str = value.strip()
        if not path_str:
            continue

        # Null-byte injection (classic path truncation attack)
        if "\0" in path_str:
            return (
                f"Path argument '{key}' contains null byte (path injection). "
                f"Tool '{tool_name}' rejected in pre-validation."
            )

        # Resolve to catch '..' traversal that survives naive checks
        try:
            resolved = os.path.normpath(path_str)
        except (TypeError, ValueError):
            return (
                f"Path argument '{key}' is not a valid path string. "
                f"Tool '{tool_name}' rejected in pre-validation."
            )

        # Path that resolves to empty after normalization is suspicious
        if not resolved or resolved == ".":
            continue

        # Always-allow list (absolute system paths, etc.)
        if any(resolved.startswith(p) for p in _ALWAYS_ALLOWED_PREFIXES):
            continue

        # Reject absolute paths that dereference /proc/self (info leak)
        if resolved.startswith("/proc/self/"):
            return (
                f"Path argument '{key}' targets /proc/self (information leak risk). "
                f"Tool '{tool_name}' rejected in pre-validation."
            )

    return None


# ---------------------------------------------------------------------------
# Pre-validation: orchestrator
# ---------------------------------------------------------------------------


@dataclass
class PreValidationResult:
    """Result of pre-validating a tool call before dispatch."""

    ok: bool
    error_message: str = ""
    tool_name: str = ""
    checks_run: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "ok": self.ok,
            "error_message": self.error_message,
            "tool_name": self.tool_name,
            "checks_run": self.checks_run,
        }


def pre_validate_tool_call(tool_name: str, args: dict) -> PreValidationResult:
    """Run all pre-validation checks on a tool call before dispatch.

    Checks (in order):
      1. Parameter size Ã¢ÂÂ reject oversized string arguments
      2. Path safety Ã¢ÂÂ reject traversal / injection in file paths

    Returns ``PreValidationResult`` Ã¢ÂÂ ``ok=True`` means all checks passed.
    The caller should short-circuit dispatch when ``ok=False``.
    """
    checks_run: list[str] = []

    # 1. Parameter size check
    checks_run.append("param_size")
    err = _check_param_size(tool_name, args)
    if err:
        logger.warning("Pre-validation FAIL [param_size] tool=%s: %s", tool_name, err)
        return PreValidationResult(ok=False, error_message=err, tool_name=tool_name, checks_run=checks_run)

    # 2. Path safety check
    checks_run.append("path_safety")
    err = _check_path_safety(tool_name, args)
    if err:
        logger.warning("Pre-validation FAIL [path_safety] tool=%s: %s", tool_name, err)
        return PreValidationResult(ok=False, error_message=err, tool_name=tool_name, checks_run=checks_run)

    return PreValidationResult(ok=True, tool_name=tool_name, checks_run=checks_run)


# ---------------------------------------------------------------------------
# Routing: tool name remapping
# ---------------------------------------------------------------------------

# Map deprecated/renamed tool names Ã¢ÂÂ current canonical names.
# Populated as tools evolve; keys are OLD names, values are NEW names.
_TOOL_REMAPS: dict[str, str] = {}

# Tools explicitly disabled regardless of registry availability.
# Set is checked before remapping; disabled tools return an error.
_DISABLED_TOOLS: set[str] = set()


def register_tool_remap(old_name: str, new_name: str) -> None:
    """Register a tool name remapping (old Ã¢ÂÂ new).

    Useful when renaming tools while maintaining backward compatibility.
    Example: ``register_tool_remap("old_search", "web_search")``
    """
    _TOOL_REMAPS[old_name] = new_name
    logger.info("Tool remap registered: '%s' Ã¢ÂÂ '%s'", old_name, new_name)


def disable_tool(tool_name: str) -> None:
    """Disable a tool by name (policy gate Ã¢ÂÂ checked before remapping)."""
    _DISABLED_TOOLS.add(tool_name)
    logger.info("Tool disabled: '%s'", tool_name)


def enable_tool(tool_name: str) -> None:
    """Re-enable a previously disabled tool."""
    _DISABLED_TOOLS.discard(tool_name)
    logger.info("Tool re-enabled: '%s'", tool_name)


def get_tool_remaps() -> dict[str, str]:
    """Return a copy of the current remap table."""
    return dict(_TOOL_REMAPS)


def get_disabled_tools() -> set[str]:
    """Return a copy of the current disabled-tool set."""
    return set(_DISABLED_TOOLS)


# ---------------------------------------------------------------------------
# Routing: capability check
# ---------------------------------------------------------------------------


def _capability_check(tool_name: str) -> Optional[str]:
    """Check whether the tool can be executed given current state.

    Returns an error string if the tool is gated, or None if it passes.

    Checks:
      1. Disabled-tool list (policy gate)
      2. Toolset availability (e.g. missing API keys)
    """
    # 1. Policy gate Ã¢ÂÂ explicitly disabled tools
    if tool_name in _DISABLED_TOOLS:
        return f"Tool '{tool_name}' is disabled by policy."

    # 2. Toolset availability Ã¢ÂÂ check via registry
    toolset = registry.get_toolset_for_tool(tool_name)
    if toolset and not registry.is_toolset_available(toolset):
        return f"Toolset '{toolset}' is unavailable (tool '{tool_name}' cannot run)."

    return None


# ---------------------------------------------------------------------------
# Routing: orchestrator
# ---------------------------------------------------------------------------


def route_tool_call(tool_name: str, args: dict) -> tuple[str, dict, Optional[str]]:
    """Apply tool routing before dispatch.

    Returns ``(canonical_name, args, error_or_none)``.

    Steps:
      1. Capability check Ã¢ÂÂ reject disabled / unavailable tools
      2. Name remapping Ã¢ÂÂ redirect deprecated names to canonical ones

    When ``error_or_none`` is not None, the caller should short-circuit
    dispatch and return the error to the model.
    """
    # 1. Capability check (on the ORIGINAL name, before remapping)
    err = _capability_check(tool_name)
    if err:
        logger.warning("Routing REJECT tool=%s: %s", tool_name, err)
        return tool_name, args, err

    # 2. Name remapping
    original = tool_name
    if tool_name in _TOOL_REMAPS:
        tool_name = _TOOL_REMAPS[tool_name]
        logger.info("Routing REMAP: '%s' → '%s'", original, tool_name)

    return tool_name, args, None
