"""Cron scheduler tick — invoked by the gateway background thread."""

from __future__ import annotations

import logging
import threading
import time
from typing import Any, Optional

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_last_warn_ts: float = 0.0


def tick(verbose: bool = False, adapters: Any = None, loop: Any = None) -> None:
    """Run one scheduler pass.

    Due jobs are detected here; full agent execution in the gateway process is not
    wired in this repository snapshot. We log at most once per minute to avoid
    spam if jobs are due.
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

    global _last_warn_ts
    with _lock:
        now_ts = time.time()
        if now_ts - _last_warn_ts < 60 and not verbose:
            return
        _last_warn_ts = now_ts

    logger.warning(
        "cron: %d job(s) due — automated execution is not wired; "
        "use `python cli.py cron run` or extend gateway/cron integration.",
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
