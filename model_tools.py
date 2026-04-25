"""Model Tools -- tool dispatch and async bridge.

This module bridges tools/registry.py (which cannot import model_tools at
module level to avoid circular imports) with the rest of the codebase.

Provides:
* ``_run_async(coro)`` -- Run an async coroutine from a sync handler.
* ``handle_function_call(name, args, task_id=None)`` -- Dispatch a tool call.
* ``get_toolset_for_tool(name)`` -- Return the toolset for a given tool.

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

import asyncio
import json
import logging

logger = logging.getLogger(__name__)

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

    If already inside a running event loop, spawns a thread to avoid
    "cannot run event loop while another is running" errors.

    Args:
        coro: An awaitable (coroutine object).

    Returns:
        The return value of the coroutine.
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(asyncio.run, coro)
            return future.result(timeout=30)
    else:
        return asyncio.run(coro)


# ---------------------------------------------------------------------------
# Tool dispatch
# ---------------------------------------------------------------------------

def handle_function_call(name, args, task_id=None):
    """Dispatch a single tool call through the central registry.

    Used by code_execution_tool's sandbox/remote-sandbox worker threads
    to execute tools without going through the full agent loop.

    Args:
        name: The name of the tool to call.
        args: The arguments dict for the tool.
        task_id: Optional task identifier for context (reserved for future use).

    Returns:
        JSON string with the tool result.
    """
    from tools.registry import registry
    return registry.dispatch(name, args)


# ---------------------------------------------------------------------------
# Registry accessors (thin wrappers for backward compat)
# ---------------------------------------------------------------------------

def get_toolset_for_tool(name):
    """Return the toolset name for a given tool, or None."""
    from tools.registry import registry
    return registry.get_toolset_for_tool(name)
