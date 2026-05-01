"""Cron scheduler tick — invoked by the gateway background thread."""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from typing import Any, Optional

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_last_warn_ts: float = 0.0

try:
    import fcntl

    _HAS_FCNTL = True
except ImportError:
    fcntl = None  # type: ignore[assignment]
    _HAS_FCNTL = False


def _acquire_tick_lock():
    from cron.jobs import JOBS_FILE

    lock_path = JOBS_FILE.parent / ".tick.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = open(lock_path, "w", encoding="utf-8")
    except OSError as exc:
        logger.debug("cron tick lock open failed: %s", exc)
        return None
    if _HAS_FCNTL:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            return fd
        except BlockingIOError:
            fd.close()
            return None
    return fd


def _release_tick_lock(fd) -> None:
    if not fd:
        return
    try:
        if _HAS_FCNTL and fcntl:
            fcntl.flock(fd, fcntl.LOCK_UN)
    except Exception:
        pass
    try:
        fd.close()
    except Exception:
        pass


def tick(
    verbose: bool = False,
    adapters: Any = None,
    loop: Any = None,
    runner: Any = None,
) -> None:
    """Run one scheduler pass.

    When *runner* and *loop* are provided (gateway process), due jobs are executed
    via ``GatewayRunner.execute_cron_job``. Otherwise due jobs only produce a
    throttled warning — use a running gateway for automatic execution.
    """
    try:
        from cron.jobs import get_due_jobs
    except Exception as exc:
        if verbose:
            logger.warning("cron tick: cannot import job module: %s", exc)
        return

    due = get_due_jobs()
    if not due:
        return

    if runner is not None and loop is not None:
        lock_fd = _acquire_tick_lock()
        if lock_fd is None:
            if verbose:
                logger.info("cron tick: skipped (lock held by another tick)")
            return
        try:

            async def _run_due() -> None:
                for job in due:
                    try:
                        await runner.execute_cron_job(job)
                    except Exception:
                        logger.exception("cron job %s failed", job.get("id"))

            fut = asyncio.run_coroutine_threadsafe(_run_due(), loop)
            try:
                fut.result(timeout=3600)
            except Exception as exc:
                logger.error("cron tick batch failed: %s", exc)
        finally:
            _release_tick_lock(lock_fd)
        return

    global _last_warn_ts
    with _lock:
        now_ts = time.time()
        if now_ts - _last_warn_ts < 60 and not verbose:
            return
        _last_warn_ts = now_ts

    logger.warning(
        "cron: %d job(s) due — start the gateway to run them automatically "
        "(this process has no event loop / runner).",
        len(due),
    )


def start_scheduler(interval: int = 60) -> None:
    """Blocking loop for standalone `python -m cron.scheduler` usage."""
    logger.info("Starting scheduler (interval=%ds)", interval)
    try:
        while True:
            tick(verbose=True)
            time.sleep(interval)
    except KeyboardInterrupt:
        logger.info("Scheduler stopped")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    tick()
