"""
Async Bridge Layer

Persistent event loops to prevent "Event loop is closed" errors when
async tool handlers (e.g., httpx/AsyncOpenAI clients) close their
transport during garbage collection.

Pattern from Hermes model_tools.py _get_tool_loop / _get_worker_loop:
- _get_tool_loop(): persistent loop for the main thread
- _get_worker_loop(): persistent per-thread loop for worker threads
- ThreadPoolExecutor: runs sync tool handlers in separate threads

Why persistent loops:
  asyncio.run() creates a loop, runs the coroutine, then *closes* the loop.
  Cached httpx/AsyncOpenAI clients remain bound to that dead loop and raise
  RuntimeError during garbage collection or subsequent use. By keeping the
  loop alive, cached clients stay valid.
"""

import asyncio
import concurrent.futures
import threading
import logging

logger = logging.getLogger(__name__)

# ── Global Thread Pool for sync tool execution ──
# Sync tool calls that internally use asyncio.run() (e.g., Modal/Docker
# terminal backends) run in this pool to get clean event loops.
_tool_executor = concurrent.futures.ThreadPoolExecutor(max_workers=128)


def resize_tool_pool(max_workers: int):
    """Replace the global tool executor with a new one of the given size."""
    global _tool_executor
    old = _tool_executor
    _tool_executor = concurrent.futures.ThreadPoolExecutor(max_workers=max_workers)
    old.shutdown(wait=False)
    logger.info("Tool thread pool resized to %d workers", max_workers)


# ── Persistent Event Loops ──

_tool_loop = None
_tool_loop_lock = threading.Lock()
_worker_thread_local = threading.local()


def get_tool_loop():
    """Return a long-lived event loop for running async tool handlers.

    Using a persistent loop (instead of asyncio.run() which creates and
    *closes* a fresh loop every time) prevents "Event loop is closed"
    errors when cached httpx/AsyncOpenAI clients attempt to close their
    transport on a dead loop during garbage collection.
    """
    global _tool_loop
    with _tool_loop_lock:
        if _tool_loop is None or _tool_loop.is_closed():
            _tool_loop = asyncio.new_event_loop()
        return _tool_loop


def get_worker_loop():
    """Return a persistent event loop for the current worker thread.

    Each worker thread gets its own long-lived loop stored in thread-local
    storage. This prevents "Event loop is closed" errors that occur when
    asyncio.run() creates + closes a loop per call, leaving cached clients
    bound to a dead loop.
    """
    loop = getattr(_worker_thread_local, 'loop', None)
    if loop is None or loop.is_closed():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        _worker_thread_local.loop = loop
    return loop


def get_tool_executor():
    """Return the global tool thread pool executor."""
    return _tool_executor
