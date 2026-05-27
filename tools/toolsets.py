#!/usr/bin/env python3
"""
MimirAether Toolsets Module

Adapted from Hermes toolsets.py — toolset definitions with include-based
composition.  Each toolset groups tools for a scenario and can include other
toolsets (recursively resolved with cycle detection).

Usage:
    from tools.toolsets import resolve_toolset, resolve_enabled_tools

    # Get tool names for a specific toolset
    tools = resolve_toolset("code")

    # Resolve enabled/disabled sets to final tool list
    tools = resolve_enabled_tools(["web", "code"], disabled=["terminal"])
"""

from typing import Dict, List, Any, Set, Optional, Callable
import logging

logger = logging.getLogger(__name__)

# ============================================================================
# Core tool list — shared by all MimirAether platform toolsets.
# Edit this once to update all platforms simultaneously.
# ============================================================================

_MIMIR_CORE_TOOLS = [
    # Web
    "web_search", "web_extract",
    # Terminal + process management
    "terminal", "process",
    # File manipulation
    "read_file", "write_file", "patch", "search_files",
    # Vision
    "vision_analyze",
    # Skills
    "skills_list", "skill_view", "skill_manage",
    # Planning & memory
    "todo", "memory",
    # Session history search
    "session_search",
    # Tool/skill discovery (ToolRanker)
    "tool_search",
    # Clarifying questions
    "clarify",
    # Code execution + delegation
    "execute_code", "delegate_task",
    # Cronjob management
    "cronjob",
    # Cross-platform messaging (gated via check_fn)
    "send_message",
    # Strategy selection
    "set_strategy", "route_strategy",
    # Home Assistant (gated via check_fn)
    "ha_list_entities", "ha_get_state", "ha_list_services", "ha_call_service",
    # Browser automation
    "browser_navigate", "browser_snapshot", "browser_click",
    "browser_type", "browser_scroll", "browser_back",
    "browser_press", "browser_get_images",
    "browser_vision", "browser_console",
    # Text-to-speech
    "text_to_speech",
    # Environment variable access
    "get_env",
    # Allowlisted ops (health / eval / session_reset — §17 P1-LONG-AUTONOMY)
    "mimir_ops",
]

# ============================================================================
# Toolset definitions
# ============================================================================

TOOLSETS: Dict[str, dict] = {
    # --- Individual tool categories (leaf toolsets) ---

    "web": {
        "description": "Web search and content extraction tools",
        "tools": ["web_search", "web_extract"],
        "includes": [],
    },

    "vision": {
        "description": "Image analysis and vision tools",
        "tools": ["vision_analyze"],
        "includes": [],
    },

    "terminal": {
        "description": "Terminal/command execution and process management",
        "tools": ["terminal", "process"],
        "includes": [],
    },

    "skills": {
        "description": "Skill document management (list, view, create, patch)",
        "tools": ["skills_list", "skill_view", "skill_manage"],
        "includes": [],
    },

    "browser": {
        "description": "Browser automation for web interaction",
        "tools": [
            "browser_navigate", "browser_snapshot", "browser_click",
            "browser_type", "browser_scroll", "browser_back",
            "browser_press", "browser_get_images",
            "browser_vision", "browser_console",
        ],
        "includes": [],
    },

    "cronjob": {
        "description": "Scheduled task management (create, list, update, trigger)",
        "tools": ["cronjob"],
        "includes": [],
    },

    "messaging": {
        "description": "Cross-platform messaging (send_message)",
        "tools": ["send_message"],
        "includes": [],
    },

    "rl": {
        "description": "RL training tools for reinforcement learning on Tinker-Atropos",
        "tools": [
            "rl_list_environments", "rl_select_environment",
            "rl_get_current_config", "rl_edit_config",
            "rl_start_training", "rl_check_status",
            "rl_stop_training", "rl_get_results",
            "rl_list_runs", "rl_test_inference",
        ],
        "includes": [],
    },

    "file": {
        "description": "File operations: read, write, patch (fuzzy matching), search, get_env",
        "tools": ["read_file", "write_file", "patch", "search_files", "get_env"],
        "includes": [],
    },

    "tts": {
        "description": "Text-to-speech synthesis",
        "tools": ["text_to_speech"],
        "includes": [],
    },

    "todo": {
        "description": "Task planning and tracking for multi-step work",
        "tools": ["todo"],
        "includes": [],
    },

    "memory": {
        "description": "Persistent memory across sessions",
        "tools": ["memory"],
        "includes": [],
    },

    "session_search": {
        "description": "Search and recall past conversations",
        "tools": ["session_search"],
        "includes": [],
    },

    "tool_search": {
        "description": "Search tools and skills by keyword or intent",
        "tools": ["tool_search"],
        "includes": [],
    },

    "clarify": {
        "description": "Ask clarifying questions to the user",
        "tools": ["clarify"],
        "includes": [],
    },

    "code_execution": {
        "description": "Execute Python code in sandbox",
        "tools": ["execute_code"],
        "includes": [],
    },

    "delegation": {
        "description": "Spawn sub-agents for complex subtasks",
        "tools": ["delegate_task"],
        "includes": [],
    },

    "homeassistant": {
        "description": "Home Assistant smart home control (gated on HASS_TOKEN)",
        "tools": [
            "ha_list_entities", "ha_get_state",
            "ha_list_services", "ha_call_service",
        ],
        "includes": [],
    },

    "mimircore": {
        "description": "MimirAether capsule system (knowledge capsules)",
        "tools": [
            "get_capsule_by_id", "list_capsules",
            "produce_capsule", "improve_capsule",
        ],
        "includes": [],
    },

    "moa": {
        "description": "Mixture of Agents — advanced multi-model reasoning",
        "tools": ["mixture_of_agents"],
        "includes": [],
    },

    # --- Scenario-specific composite toolsets ---

    "debugging": {
        "description": "Debugging toolkit (terminal + web search + file ops)",
        "tools": [],
        "includes": ["terminal", "web", "file"],
    },

    "safe": {
        "description": "Safe toolkit without terminal access",
        "tools": [],
        "includes": ["web", "vision", "file", "skills", "memory"],
    },

    "code": {
        "description": "Full code development toolkit",
        "tools": [],
        "includes": ["code_execution", "file", "terminal", "web", "skills"],
    },

    "research": {
        "description": "Research toolkit (web + vision + file + memory)",
        "tools": [],
        "includes": ["web", "vision", "file", "memory", "session_search"],
    },

    # --- Platform toolsets ---

    "mimir-feishu": {
        "description": "MimirAether Feishu bot — full toolkit",
        "tools": _MIMIR_CORE_TOOLS,
        "includes": [],
    },

    "mimir-cli": {
        "description": "MimirAether CLI — full toolkit",
        "tools": _MIMIR_CORE_TOOLS,
        "includes": [],
    },
}


# ============================================================================
# Resolution functions
# ============================================================================

def _get_registry_toolset_names() -> Set[str]:
    """Return toolset names registered in the live registry."""
    try:
        from tools.registry import registry
        return set(registry.get_registered_toolset_names())
    except Exception:
        return set()


def get_toolset(name: str) -> Optional[Dict[str, Any]]:
    """Get a toolset definition by name.

    Also merges tools from the live registry for the matching toolset.
    Returns None if the toolset is not found.
    """
    toolset = TOOLSETS.get(name)

    try:
        from tools.registry import registry
    except Exception:
        return toolset

    if toolset:
        merged_tools = sorted(
            set(toolset.get("tools", []))
            | set(registry.get_tool_names_for_toolset(name))
        )
        return {**toolset, "tools": merged_tools}

    # Auto-generate for registry-only toolsets (MCP, plugins)
    registry_tools = registry.get_tool_names_for_toolset(name)
    if registry_tools:
        return {
            "description": f"Plugin/registry toolset: {name}",
            "tools": registry_tools,
            "includes": [],
        }
    return None


def resolve_toolset(name: str, visited: Set[str] = None) -> List[str]:
    """Recursively resolve a toolset to all tool names.

    Handles toolset composition via ``includes`` and detects cycles.
    ``"all"`` or ``\"*\"`` resolves to every known tool.
    """
    if visited is None:
        visited = set()

    # "all" / "*" → union of every toolset
    if name in {"all", "*"}:
        all_tools: Set[str] = set()
        for ts_name in get_toolset_names():
            resolved = resolve_toolset(ts_name, visited.copy())
            all_tools.update(resolved)
        return sorted(all_tools)

    # Diamond / cycle guard
    if name in visited:
        return []
    visited.add(name)

    toolset = get_toolset(name)
    if not toolset:
        return []

    tools = set(toolset.get("tools", []))

    for included_name in toolset.get("includes", []):
        included_tools = resolve_toolset(included_name, visited)
        tools.update(included_tools)

    return sorted(tools)


def resolve_multiple_toolsets(toolset_names: List[str]) -> List[str]:
    """Resolve multiple toolsets and combine their tools (deduplicated)."""
    all_tools: Set[str] = set()
    for name in toolset_names:
        all_tools.update(resolve_toolset(name))
    return sorted(all_tools)


def resolve_enabled_tools(
    enabled: List[str] = None,
    disabled: List[str] = None,
) -> List[str]:
    """Resolve a final tool list from enabled / disabled toolset names.

    * If *enabled* is empty/None, resolves ``["all"]`` (backward compat).
    * Tools from *disabled* toolsets are subtracted at the end.
    """
    if not enabled:
        all_tools = resolve_toolset("all")
    else:
        all_tools = resolve_multiple_toolsets(enabled)

    if disabled:
        disabled_tools = resolve_multiple_toolsets(disabled)
        all_tools = sorted(set(all_tools) - set(disabled_tools))

    return all_tools


# ============================================================================
# Query helpers
# ============================================================================

def get_all_toolsets() -> Dict[str, Dict[str, Any]]:
    """Get all toolset definitions (static + registry-discovered)."""
    result = dict(TOOLSETS)
    for ts_name in _get_registry_toolset_names():
        if ts_name in result:
            continue
        ts_def = get_toolset(ts_name)
        if ts_def:
            result[ts_name] = ts_def
    return result


def get_toolset_names() -> List[str]:
    """Return sorted names of all known toolsets."""
    names = set(TOOLSETS.keys()) | _get_registry_toolset_names()
    return sorted(names)


def validate_toolset(name: str) -> bool:
    """Check whether *name* is a valid toolset."""
    if name in {"all", "*"}:
        return True
    if name in TOOLSETS:
        return True
    return name in _get_registry_toolset_names()


def create_custom_toolset(
    name: str,
    description: str,
    tools: List[str] = None,
    includes: List[str] = None,
) -> None:
    """Create a custom toolset at runtime (does not persist)."""
    TOOLSETS[name] = {
        "description": description,
        "tools": tools or [],
        "includes": includes or [],
    }


def get_toolset_info(name: str) -> Optional[Dict[str, Any]]:
    """Get detailed info about a toolset including resolved tools."""
    toolset = get_toolset(name)
    if not toolset:
        return None

    resolved_tools = resolve_toolset(name)
    return {
        "name": name,
        "description": toolset["description"],
        "direct_tools": toolset["tools"],
        "includes": toolset["includes"],
        "resolved_tools": resolved_tools,
        "tool_count": len(resolved_tools),
        "is_composite": bool(toolset["includes"]),
    }
