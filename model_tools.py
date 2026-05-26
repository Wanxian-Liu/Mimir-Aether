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
        "tools.mimir_ops_tool",
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

    LLMs frequently return numbers as strings (``\"42\"`` instead of ``42``)
    and booleans as strings (``\"true\"`` instead of ``true``).  This compares
    each argument value against the tool's registered JSON Schema and attempts
    safe coercion when the value is a string but the schema expects a different
    type.  Original values are preserved when coercion fails.

    Handles ``\"type\": \"integer\"``, ``\"type\": \"number\"``, ``\"type\": \"boolean\"``,
    and union types (``\"type\": [\"integer\", \"string\"]``).

    Also wraps bare scalar values in a single-element list when the schema
    declares ``\"type\": \"array\"``.  Open-weight models sometimes emit
    ``{\"urls\": \"https://a.com\"}`` when the tool expects
    ``{\"urls\": [\"https://a.com\"]}``; wrapping here avoids a confusing tool
    failure on what is otherwise a well-formed call.

    Hermes-compatible implementation (model_tools.py L501-582).
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

    for key, value in list(args.items()):
        prop_schema = properties.get(key)
        if not prop_schema:
            continue
        expected = prop_schema.get("type")

        # Wrap bare non-list values when the schema declares ``array``.
        # Strings still go through _coerce_value first so JSON-encoded
        # arrays (``'[\"a\",\"b\"]'``) get parsed and nullable ``\"null\"``
        # becomes ``None`` rather than ``[\"null\"]``.
        # ``None`` itself is preserved.
        if expected == "array" and value is not None and not isinstance(value, (list, tuple)):
            if isinstance(value, str):
                coerced = _coerce_value(value, expected, schema=prop_schema)
                if coerced is not value:
                    args[key] = coerced
                    continue
                if value.strip().startswith("["):
                    logger.warning(
                        "coerce_tool_args: %s.%s looks like a JSON array string "
                        "but could not be parsed — model may have emitted a "
                        "JSON-encoded string instead of a native array. "
                        "Falling back to single-element list.",
                        tool_name, key,
                    )
                args[key] = [value]
                logger.info(
                    "coerce_tool_args: wrapped bare string in list for %s.%s",
                    tool_name, key,
                )
                continue
            args[key] = [value]
            logger.info(
                "coerce_tool_args: wrapped bare %s in list for %s.%s",
                type(value).__name__, tool_name, key,
            )
            continue

        if not isinstance(value, str):
            continue
        if not expected and not _schema_allows_null(prop_schema):
            continue
        coerced = _coerce_value(value, expected, schema=prop_schema)
        if coerced is not value:
            args[key] = coerced

    return args


def _coerce_value(value, expected_type, schema=None):
    """Attempt to coerce a string *value* to *expected_type*.

    Returns the original string when coercion is not applicable or fails.
    """
    if _schema_allows_null(schema) and value.strip().lower() == "null":
        return None

    if isinstance(expected_type, list):
        # Union type — try each in order, return first successful coercion
        for t in expected_type:
            result = _coerce_value(value, t, schema=schema)
            if result is not value:
                return result
        return value

    if expected_type in {"integer", "number"}:
        return _coerce_number(value, integer_only=(expected_type == "integer"))
    if expected_type == "boolean":
        return _coerce_boolean(value)
    if expected_type == "array":
        return _coerce_json(value, list)
    if expected_type == "object":
        return _coerce_json(value, dict)
    if expected_type == "null" and value.strip().lower() == "null":
        return None
    return value


def _schema_allows_null(schema):
    """Return True when a JSON Schema fragment explicitly permits null."""
    if not isinstance(schema, dict):
        return False

    schema_type = schema.get("type")
    if schema_type == "null":
        return True
    if isinstance(schema_type, list) and "null" in schema_type:
        return True
    if schema.get("nullable") is True:
        return True

    for union_key in ("anyOf", "oneOf"):
        variants = schema.get(union_key)
        if not isinstance(variants, list):
            continue
        for variant in variants:
            if isinstance(variant, dict) and variant.get("type") == "null":
                return True

    return False


def _coerce_json(value, expected_python_type):
    """Parse *value* as JSON when the schema expects an array or object.

    Handles model output drift where a complex oneOf/discriminated-union
    schema causes the LLM to emit the array/object as a JSON string instead
    of a native structure.  Returns the original string if parsing fails or
    yields the wrong Python type.
    """
    try:
        parsed = json.loads(value)
    except (ValueError, TypeError) as exc:
        logger.warning(
            "coerce_tool_args: failed to parse string as JSON for expected type %s: %s",
            expected_python_type.__name__,
            exc,
        )
        return value
    if isinstance(parsed, expected_python_type):
        logger.debug(
            "coerce_tool_args: coerced string to %s via json.loads",
            expected_python_type.__name__,
        )
        return parsed
    logger.warning(
        "coerce_tool_args: JSON-parsed value is %s, expected %s — skipping coercion",
        type(parsed).__name__,
        expected_python_type.__name__,
    )
    return value


def _coerce_number(value, integer_only=False):
    """Try to parse *value* as a number.  Returns original string on failure."""
    try:
        f = float(value)
    except (ValueError, OverflowError):
        return value
    # Guard against inf/nan — not JSON-serializable, keep original string
    if f != f or f == float("inf") or f == float("-inf"):
        return value
    # If it looks like an integer (no fractional part), return int
    if f == int(f):
        return int(f)
    if integer_only:
        # Schema wants an integer but value has decimals — keep as string
        return value
    return f


def _coerce_boolean(value):
    """Try to parse *value* as a boolean.  Returns original string on failure."""
    low = value.strip().lower()
    if low == "true":
        return True
    if low == "false":
        return False
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
