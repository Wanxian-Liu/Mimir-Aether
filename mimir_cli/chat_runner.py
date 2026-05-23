"""Chat entry for ``mimir chat`` without importing legacy ``cli.main`` (E-005 / E-008).

Delegates to ``mimir_cli.task_runner`` for one-shot and interactive chat.
"""

from __future__ import annotations

import asyncio
import inspect
import os
import sys
from typing import Any


def _resolve_model(args: Any) -> str:
    if getattr(args, "model", None):
        return args.model
    from mimicore.config.model_defaults import get_model

    return get_model()


def _resolve_max_iterations(args: Any) -> int:
    max_turns = getattr(args, "max_turns", None)
    if max_turns is not None:
        return int(max_turns)
    try:
        from mimir_cli.config import load_config

        cfg = load_config() or {}
        agent = cfg.get("agent") or {}
        if "max_turns" in agent:
            return int(agent["max_turns"])
        if "max_turns" in cfg:
            return int(cfg["max_turns"])
    except Exception:
        pass
    return 90


def apply_chat_env(args: Any) -> None:
    """Map ``mimir chat`` flags to process env consumed by agent/tools."""
    if getattr(args, "source", None):
        os.environ["HERMES_SESSION_SOURCE"] = str(args.source)

    resume = getattr(args, "resume", None)
    if resume:
        os.environ["HERMES_SESSION_ID"] = str(resume)

    max_iters = _resolve_max_iterations(args)
    os.environ["HERMES_MAX_ITERATIONS"] = str(max_iters)

    if getattr(args, "checkpoints", False):
        os.environ["HERMES_CHECKPOINTS"] = "1"

    if getattr(args, "worktree", False):
        os.environ["HERMES_WORKTREE"] = "1"

    if getattr(args, "pass_session_id", False):
        os.environ["HERMES_PASS_SESSION_ID"] = "1"


def run_chat(args: Any) -> None:
    """Run chat or one-shot query. Raises ``SystemExit`` on user-facing errors."""
    apply_chat_env(args)

    query = getattr(args, "query", None)
    verbose = bool(getattr(args, "verbose", False))
    model = _resolve_model(args)
    max_iterations = _resolve_max_iterations(args)

    if query:
        from mimir_cli.task_runner import run_task

        rc = asyncio.run(
            run_task(
                task=query,
                model=model,
                max_iterations=max_iterations,
                verbose=verbose,
            )
        )
        raise SystemExit(rc or 0)

    from mimir_cli.task_runner import run_interactive

    rc = asyncio.run(run_interactive())
    raise SystemExit(rc or 0)


def cmd_chat_does_not_import_cli_main() -> bool:
    """True when ``mimir_cli.main.cmd_chat`` no longer imports ``cli.main``."""
    from mimir_cli import main as mimir_main

    source = inspect.getsource(mimir_main.cmd_chat)
    return "cli.main" not in source and "cli import main" not in source
