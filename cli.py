#!/usr/bin/env python3
"""Legacy entry shim — prefer ``python -m mimir_cli`` or ``mimir`` (E-008)."""

from __future__ import annotations

import sys

from mimir_cli.main import main
from mimir_cli.task_runner import run_interactive, run_task

__all__ = ["main", "run_task", "run_interactive"]

if __name__ == "__main__":
    raise SystemExit(main() or 0)
def broken_fu