"""
Async Bridge Layer

Persistent event loops to prevent "Event loop is closed" errors when
async tool handlers (e.g., httpx/AsyncOpenAI clients) close their
transport during garbage collection.

Pattern from Hermes model_tools.py _get_tool_loop / _get_worker_loop:
- _get_tool_loop(): persistent loop for the main thread
- _get_worker_loop(): persistent per-thread loop for worker threads
- _run_async(): sync→async bridge, detects event loop context
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


def run_async(coro):
    """Run a coroutine from synchronous code, handling event loop context.

    Three cases handled:
    1. No running event loop, main thread (CLI / sync path)
       → uses the persistent tool_loop via get_tool_loop()
    2. Running event loop (inside an async handler calling sync→async)
       → defers to the thread pool executor (300s timeout)
    3. No running event loop, worker thread (non-main)
       → uses a per-thread persistent loop via get_worker_loop()

    This is the bridge between sync tool dispatch (registry.dispatch)
    and async tool handlers (httpx, AsyncOpenAI, etc.).

    Pattern from Hermes model_tools.py _run_async().
    """
    try:
        running_loop = asyncio.get_running_loop()
    except RuntimeError:
        running_loop = None

    if running_loop and running_loop.is_running():
        # Inside a running event loop — can't use run_until_complete().
        # Spawn a fresh thread with its own persistent event loop so:
        #   - cached httpx/AsyncOpenAI clients stay bound to a live loop
        #   - the loop lives for the coroutine's full lifetime
        #   - on timeout we cancel the coroutine inside its own loop
        #     so the worker thread can wind down instead of leaking.
        worker_loop: asyncio.AbstractEventLoop | None = None
        loop_ready = threading.Event()

        def _run_in_worker():
            nonlocal worker_loop
            worker_loop = asyncio.new_event_loop()
            loop_ready.set()
            try:
                asyncio.set_event_loop(worker_loop)
                return worker_loop.run_until_complete(coro)
            finally:
                # Cancel pending tasks so the loop can close cleanly
                try:
                    pending = asyncio.all_tasks(worker_loop)
                    for t in pending:
                        t.cancel()
                    if pending:
                        worker_loop.run_until_complete(
                            asyncio.gather(*pending, return_exceptions=True)
                        )
                except Exception:
                    pass
                worker_loop.close()

        pool = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        future = pool.submit(_run_in_worker)
        try:
            return future.result(timeout=300)
        except concurrent.futures.TimeoutError:
            # Cancel the coroutine inside its own loop so the worker
            # thread can wind down instead of running forever.
            if loop_ready.wait(timeout=1.0) and worker_loop is not None:
                try:
                    for t in asyncio.all_tasks(worker_loop):
                        worker_loop.call_soon_threadsafe(t.cancel)
                except RuntimeError:
                    pass
            raise
        finally:
            pool.shutdown(wait=False)
    else:
        # Worker thread (non-main thread without running loop) — use a
        # per-thread persistent loop to avoid contention with the main
        # thread's loop. asyncio event loops are not thread-safe, so
        # each worker thread must have its own.
        if threading.current_thread() is not threading.main_thread():
            worker_loop = get_worker_loop()
            return worker_loop.run_until_complete(coro)
        # Sync context (CLI main thread path): use the persistent tool loop.
        loop = get_tool_loop()
        return loop.run_until_complete(coro)


def get_tool_executor():
    """Return the global tool thread pool executor."""
    return _tool_executor
