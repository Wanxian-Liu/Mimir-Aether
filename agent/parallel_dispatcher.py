"""
Parallel tool dispatcher for MimirAether.

Classifies tool calls as read-only (parallel-safe) or side-effect (must be serial),
then dispatches accordingly.

Usage:
    dispatcher = ParallelToolDispatcher()
    results = await dispatcher.dispatch_all(tool_calls, loop, executor, tool_dispatcher)
"""

import asyncio
import json
import logging
import os
from typing import Any, Callable, Dict, List, Set

logger = logging.getLogger(__name__)

def parallel_tools_enabled() -> bool:
    """Check if parallel tool dispatch is enabled (reads env at call time)."""
    return os.environ.get("MIMIR_PARALLEL_TOOLS", "0") == "1"


# Read-only tools (parallel-safe, no side effects)
_READ_ONLY_TOOLS: Set[str] = {
    "search_files",
    "read_file",
    "web_search",
    "web_extract",
    "browser_snapshot",
    "browser_console",
    "browser_get_images",
    "get_capsule_by_id",
    "list_capsules",
    "skills_list",
    "tool_search",
    "session_search",
    "vision_analyze",
}


def is_read_only(tool_name: str) -> bool:
    """Check if a tool is read-only and safe for parallel execution."""
    return tool_name in _READ_ONLY_TOOLS


async def dispatch_all(
    tool_calls: List[Dict[str, Any]],
    executor: "concurrent.futures.ThreadPoolExecutor",
    tool_dispatcher: Callable[[str, dict, str], str],
    task_id: str = "",
) -> List[Any]:
    """Dispatch tool calls, running read-only tools in parallel.


    Args:
        tool_calls: List of normalized tool call dicts with keys:
                    id, type, function.name, function.arguments
        executor: ThreadPoolExecutor for sync tool dispatcher
        tool_dispatcher: Callable[[tool_name, args, task_id], str]
        task_id: Session/task identifier for logging

    Returns:
        List of (tool_name, tool_call_id, raw_args, tool_result) tuples
        in the same order as tool_calls.
    """
    # Classify
    ro_indices: List[int] = []
    serial_indices: List[int] = []
    for i, tc in enumerate(tool_calls):
        name = tc.get("function", {}).get("name", "")
        if is_read_only(name):
            ro_indices.append(i)
        else:
            serial_indices.append(i)

    logger.info(
        "[%s] parallel dispatch: %d read-only, %d serial (total %d)",
        task_id[:8] if task_id else "", len(ro_indices), len(serial_indices),
        len(tool_calls),
    )

    results: List[Any] = [None] * len(tool_calls)

    # --- Execute read-only tools in parallel ---
    if ro_indices:
        ro_specs = [(i, tool_calls[i]) for i in ro_indices]

        async def _run_one(idx: int, tc: dict) -> tuple:
            name = tc.get("function", {}).get("name", "")
            raw_args = tc.get("function", {}).get("arguments", "{}")
            tid = tc.get("id", "")
            try:
                args = json.loads(raw_args) if isinstance(raw_args, str) else (raw_args or {})
            except Exception:
                args = {}
            # P0-1 (2026-08-19): per-tool 超时 + 单工具 retry（不重试全部——失败隔离）
            # B1 (2026-08-19 v2): retry 由独立 env MIMIR_PARALLEL_RETRY 控制（默认 1=启用）
            retry_enabled = os.getenv("MIMIR_PARALLEL_RETRY", "1").strip().lower() not in ("0", "false", "no", "off")
            timeout_s = float(os.environ.get("MIMIR_TOOL_TIMEOUT", "60"))
            max_retries = int(os.environ.get("MIMIR_TOOL_RETRY", "1"))

            async def _invoke() -> Any:
                return await asyncio.get_running_loop().run_in_executor(
                    executor,
                    lambda n=name, a=args, tid=tid: tool_dispatcher(n, a, tid),
                )

            attempts = max_retries + 1 if retry_enabled else 1
            last_err: Exception = None
            for attempt in range(attempts):
                try:
                    result = await asyncio.wait_for(_invoke(), timeout=timeout_s)
                    if attempt > 0:
                        logger.warning(
                            "[%s] parallel tool %s retry %d OK (was %s)",
                            task_id[:8] if task_id else "", name, attempt, type(last_err).__name__,
                        )
                    return (name, tid, raw_args, result)
                except asyncio.TimeoutError:
                    last_err = TimeoutError(f"{name} timed out after {timeout_s}s")
                    logger.warning(
                        "[%s] parallel tool %s timeout (%.0fs) attempt %d/%d",
                        task_id[:8] if task_id else "", name, timeout_s, attempt + 1, attempts,
                    )
                except Exception as e:
                    last_err = e
                    logger.warning(
                        "[%s] parallel tool %s failed (attempt %d/%d): %s",
                        task_id[:8] if task_id else "", name, attempt + 1, attempts, e,
                    )
            # 全部尝试失败——返回错误（不中断其他并行工具）
            raise last_err if last_err else RuntimeError(f"{name} failed")

        ro_futures = [_run_one(i, tc) for i, tc in ro_specs]
        ro_outcomes = await asyncio.gather(*ro_futures, return_exceptions=True)

        for spec, outcome in zip(ro_specs, ro_outcomes):
            idx = spec[0]
            if isinstance(outcome, Exception):
                logger.error("[%s] parallel tool %d failed: %s", task_id[:8] if task_id else "", idx, outcome)
                results[idx] = (tool_calls[idx], outcome)
            else:
                results[idx] = outcome

    # --- Execute serial tools one by one ---
    for i in serial_indices:
        tc = tool_calls[i]
        name = tc.get("function", {}).get("name", "")
        raw_args = tc.get("function", {}).get("arguments", "{}")
        tid = tc.get("id", "")
        try:
            args = json.loads(raw_args) if isinstance(raw_args, str) else (raw_args or {})
        except Exception:
            args = {}
        try:
            result = await asyncio.get_running_loop().run_in_executor(
                executor,
                lambda n=name, a=args, tid=tid: tool_dispatcher(n, a, tid),
            )
            results[i] = (name, tid, raw_args, result)
        except Exception as e:
            logger.error("[%s] serial tool %s failed: %s", task_id[:8] if task_id else "", name, e)
            results[i] = (name, tid, raw_args, json.dumps({"error": f"{type(e).__name__}: {e}"}))

    return results
