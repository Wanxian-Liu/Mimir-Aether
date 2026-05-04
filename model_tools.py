"""Model Tools -- tool dispatch and async bridge.

This module bridges tools/registry.py (which cannot import model_tools at
module level to avoid circular imports) with the rest of the codebase.

Provides:
* ``_run_async(coro)`` -- Run an async coroutine from a sync handler.
* ``handle_function_call(name, args, task_id=None)`` -- Dispatch a tool call.
* ``get_toolset_for_tool(name)`` -- Return the toolset for a given tool.
* ``_discover_tools()`` -- Import all tool modules to trigger registry.register()

Module-level state:
* ``_last_resolved_tool_names`` -- Tracks the last set of tool names resolved
  during agent initialization.  Used by delegate_tool to save/restore parent
  tool names when child agents mutate the global.

Import chain (circular-import safe):
    tools/registry.py  (no imports from model_tools or tool files)
           ^
    tools/*.py  (import from tools.registry at module level)
           ^
    model_tools.py  (imports tools.registry + all tool modules)
           ^
    run_agent.py, cli.py, batch_runner.py, etc.
"""

from agent.async_bridge import run_async
import importlib
import json
import logging

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Tool Discovery (importing each module triggers its registry.register calls)
# ---------------------------------------------------------------------------

def _discover_tools():
    """Import all tool modules to trigger their registry.register() calls.
    
    Wrapped in a function so import errors in optional tools (e.g., fal_client
    not installed) don't prevent the rest from loading.
    
    Based on Hermes' _discover_tools() implementation.
    """
    _modules = [
        "tools.builtin",  # Built-in tools (read_file, write_file, execute_code, etc.)
        "tools.strategy",  # Strategy framework + tool dispatch pre-validation/routing
        "tools.web_tools",
        "tools.terminal_tool",
        "tools.file_tools",
        "tools.vision_tools",
        "tools.mixture_of_agents_tool",
        "tools.image_generation_tool",  # fal_client not installed - expected to fail
        "tools.skill_manager_tool",
        "tools.browser_tool",
        "tools.cronjob_tools",
        "tools.rl_training_tool",
        "tools.tts_tool",
        "tools.todo_tool",
        "tools.memory_tool",
        "tools.session_search_tool",
        "tools.clarify_tool",
        "tools.code_execution_tool",
        "tools.delegate_tool",
        "tools.process_registry",
        "tools.send_message_tool",
        "tools.homeassistant_tool",
    ]
    for mod_name in _modules:
        try:
            importlib.import_module(mod_name)
        except Exception as e:
            logger.warning("Could not import tool module %s: %s", mod_name, e)


# Run tool discovery at module load time
_discover_tools()

# Hermes name alignment: legacy ``search_web`` (removed from tools.builtin) → ``web_search``.
from tools.strategy import register_tool_remap

register_tool_remap("search_web", "web_search")


# ---------------------------------------------------------------------------
# Module-level state
# ---------------------------------------------------------------------------

_last_resolved_tool_names: list = []
"""Tracks the last set of resolved tool names from tool definition resolution.

Populated during AIAgent.__init__ -> get_tool_definitions().
delegate_tool saves/restores this when spawning child agents so the parent's
toolset is not corrupted by child initialization.
"""


# ---------------------------------------------------------------------------
# Sync/async bridge
# ---------------------------------------------------------------------------

def _run_async(coro):
    """Run an async coroutine from a sync handler.

    Delegates to agent.async_bridge.run_async() which uses persistent
    event loops (Hermes pattern) instead of creating+closing a fresh
    loop per call via asyncio.run(). This prevents "Event loop is closed"
    errors from cached httpx/AsyncOpenAI clients.

    Args:
        coro: An awaitable (coroutine object).

    Returns:
        The return value of the coroutine.
    """
    return run_async(coro)


# ---------------------------------------------------------------------------
# Tool dispatch
# ---------------------------------------------------------------------------

def coerce_tool_args(tool_name, args):
    """Coerce tool call arguments to match their JSON Schema types.
    
    LLMs frequently return numbers as strings ("42" instead of 42)
    and booleans as strings ("true" instead of true). This compares
    each argument value against the tool's registered JSON Schema and
    attempts safe coercion when the value is a string but the schema
    expects a different type.
    
    Based on Hermes' coerce_tool_args implementation.
    """
    if not args or not isinstance(args, dict):
        return args
    
    from tools.registry import registry
    schema = registry.get_schema(tool_name)
    if not schema:
        return args
    
    properties = (schema.get("parameters") or {}).get("properties")
    if not properties:
        return args
    
    for key, value in args.items():
        if not isinstance(value, str):
            continue
        prop_schema = properties.get(key)
        if not prop_schema:
            continue
        expected = prop_schema.get("type")
        if not expected:
            continue
        coerced = _coerce_value(value, expected)
        if coerced is not value:
            args[key] = coerced
    
    return args


def _coerce_value(value, expected_type):
    """Attempt to coerce a string value to expected type."""
    if isinstance(expected_type, list):
        for t in expected_type:
            result = _coerce_value(value, t)
            if result is not None:
                return result
        return value
    
    if expected_type == "integer":
        try:
            return int(value)
        except (ValueError, TypeError):
            return value
    elif expected_type == "number":
        try:
            return float(value)
        except (ValueError, TypeError):
            return value
    elif expected_type == "boolean":
        if value.lower() in ("true", "1", "yes"):
            return True
        elif value.lower() in ("false", "0", "no"):
            return False
        return value
    elif expected_type == "array":
        try:
            import json
            return json.loads(value)
        except (ValueError, TypeError):
            return value
    elif expected_type == "object":
        try:
            import json
            return json.loads(value)
        except (ValueError, TypeError):
            return value
    
    return value


def handle_function_call(name, args, task_id=None):
    """Dispatch a single tool call through the central registry.

    Used by code_execution_tool's sandbox/remote-sandbox worker threads
    to execute tools without going through the full agent loop.

    Integrated strategy layer (tools.strategy):
      1. Pre-validate  — param size limits, path safety
      2. Route         — capability gating, tool name remapping
      3. Coerce        — align args with JSON Schema types
      4. Dispatch      — registry.dispatch()

    Args:
        name: The name of the tool to call.
        args: The arguments dict for the tool.
        task_id: Optional task identifier for context (reserved for future use).

    Returns:
        JSON string with the tool result.
    """
    # 1. Pre-validation (param size, path safety)
    from tools.strategy import pre_validate_tool_call, route_tool_call

    pre_result = pre_validate_tool_call(name, args)
    if not pre_result.ok:
        logger.warning(
            "Tool dispatch PRE-VALIDATION FAIL tool=%s: %s",
            name, pre_result.error_message,
        )
        return json.dumps({"error": pre_result.error_message, "type": "pre_validation_error"})

    # 2. Routing (capability check, name remapping)
    name, args, routing_error = route_tool_call(name, args)
    if routing_error:
        logger.warning(
            "Tool dispatch ROUTING FAIL tool=%s: %s",
            name, routing_error,
        )
        return json.dumps({"error": routing_error, "type": "routing_error"})

    # 3. Coerce arguments to match schema types
    args = coerce_tool_args(name, args)

    # 4. Dispatch
    from tools.registry import registry
    return registry.dispatch(name, args)


# ---------------------------------------------------------------------------
# Registry accessors (thin wrappers for backward compat)
# ---------------------------------------------------------------------------

def get_toolset_for_tool(name):
    """Return the toolset name for a given tool, or None."""
    from tools.registry import registry
    return registry.get_toolset_for_tool(name)
