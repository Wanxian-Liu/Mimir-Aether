#!/usr/bin/env python3
"""
Pi Subagent Bridge for MimirAether.

Spawns pi subagents via subprocess and returns structured results.
Minimal — no framework dependencies, just subprocess + JSON.

Usage:
    from subagent_bridge import spawn_subagent
    
    result = spawn_subagent(
        type="Explore",
        prompt="ls ~/wiki/concepts/*.md | head -5",
        tools_list=["read", "bash", "grep", "find", "ls"],
    )
    print(json.dumps(result, indent=2))
"""

import asyncio
import json
import os
import subprocess
import sys
from dataclasses import dataclass, field
from typing import Optional

# ── Constants ──────────────────────────────────────────────
PI_PATH = os.path.expanduser("~/.bun/bin")
PI_BIN = os.path.join(PI_PATH, "pi")
if not os.path.isfile(PI_BIN):
    PI_BIN = "pi"  # fallback to PATH lookup
MIMIR_ENV = os.path.expanduser("~/.mimiraether/.env")

# Model mapping: subagent_type → pi model arg
TYPE_MODEL_MAP = {
    "Explore": "deepseek/deepseek-v4-flash",
    "Plan": "deepseek/deepseek-v4-pro",
    "general-purpose": "deepseek/deepseek-v4-pro",
}


@dataclass
class SubagentResult:
    """Structured result from a pi subagent invocation."""
    success: bool
    type: str
    prompt: str
    stdout: str = ""
    stderr: str = ""
    exit_code: int = -1
    model: str = ""
    error: Optional[str] = None


def _load_env() -> dict[str, str]:
    """Load MimirAether .env into a dict, merging with current os.environ."""
    env = os.environ.copy()
    env["PATH"] = f"{PI_PATH}:{env.get('PATH', '')}"
    if os.path.isfile(MIMIR_ENV):
        with open(MIMIR_ENV) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, _, v = line.partition("=")
                env[k.strip()] = v.strip().strip('"').strip("'")
    return env


def spawn_subagent(
    type: str,
    prompt: str,
    tools_list: Optional[list[str]] = None,
    model: Optional[str] = None,
    max_turns: int = 30,
    timeout: int = 300,
) -> SubagentResult:
    """Spawn a pi subagent and wait for its result.

    Args:
        type: Subagent type — "Explore", "Plan", or "general-purpose".
        prompt: The task description for the subagent.
        tools_list: Restrict tools (default: all available).
        model: Override model. Falls back to TYPE_MODEL_MAP.
        max_turns: Max agentic turns before abort.
        timeout: Max wall-clock seconds for the subprocess.

    Returns:
        SubagentResult with success, stdout, stderr, exit_code.
    """
    model = model or TYPE_MODEL_MAP.get(type, "deepseek/deepseek-v4-pro")
    env = _load_env()

    # Build pi CLI args
    cmd = [
        PI_BIN,
        "--provider", "deepseek",
        "--model", model,
        # 非交互模式：pi 默认交互 TUI，在 subprocess 中会挂起等待输入直到超时。
        # --print 让 pi 处理完 prompt 即退出（2026-08-12 P1-3.1 修复）。
        "--print",
    ]
    # NOTE: pi does not support --max-turns or --tools as CLI flags.
    # Tool restrictions and turn limits are enforced via custom agent .md files
    # in ~/.pi/agents/<type>.md, not via CLI arguments.

    cmd.append(prompt)

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
            cwd=os.path.expanduser("~"),
        )
        return SubagentResult(
            success=(proc.returncode == 0),
            type=type,
            prompt=prompt,
            stdout=proc.stdout.strip(),
            stderr=proc.stderr.strip(),
            exit_code=proc.returncode,
            model=model,
        )
    except subprocess.TimeoutExpired:
        return SubagentResult(
            success=False,
            type=type,
            prompt=prompt,
            error=f"Timeout after {timeout}s",
            model=model,
        )
    except FileNotFoundError:
        return SubagentResult(
            success=False,
            type=type,
            prompt=prompt,
            error=f"pi binary not found. Install: bun add -g @earendil-works/pi-coding-agent",
            model=model,
        )
    except Exception as e:
        return SubagentResult(
            success=False,
            type=type,
            prompt=prompt,
            error=str(e),
            model=model,
        )


async def _spawn_async(
    type: str,
    prompt: str,
    tools_list: Optional[list[str]] = None,
    model: Optional[str] = None,
    max_turns: int = 30,
    timeout: int = 300,
) -> SubagentResult:
    """Async version of spawn_subagent — runs pi subprocess without blocking.

    Used by spawn_dual() for true parallelism via asyncio.gather().
    """
    model = model or TYPE_MODEL_MAP.get(type, "deepseek/deepseek-v4-pro")
    env = _load_env()

    cmd = [
        PI_BIN,
        "--provider", "deepseek",
        "--model", model,
        # 非交互模式（同上）
        "--print",
    ]
    cmd.append(prompt)

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
            cwd=os.path.expanduser("~"),
        )
        stdout_bytes, stderr_bytes = await asyncio.wait_for(
            proc.communicate(), timeout=timeout
        )
        return SubagentResult(
            success=(proc.returncode == 0),
            type=type,
            prompt=prompt,
            stdout=stdout_bytes.decode("utf-8", errors="replace").strip(),
            stderr=stderr_bytes.decode("utf-8", errors="replace").strip(),
            exit_code=proc.returncode or -1,
            model=model,
        )
    except asyncio.TimeoutError:
        return SubagentResult(
            success=False,
            type=type,
            prompt=prompt,
            error=f"Timeout after {timeout}s",
            model=model,
        )
    except FileNotFoundError:
        return SubagentResult(
            success=False,
            type=type,
            prompt=prompt,
            error="pi binary not found. Install: bun add -g @earendil-works/pi-coding-agent",
            model=model,
        )
    except Exception as e:
        return SubagentResult(
            success=False,
            type=type,
            prompt=prompt,
            error=str(e),
            model=model,
        )


def spawn_dual(
    explore_prompt: str,
    verify_prompt: str,
    explore_model: str = "deepseek/deepseek-v4-flash",
    verify_model: str = "deepseek/deepseek-v4-pro",
    explore_type: str = "Explore",
    verify_type: str = "general-purpose",
    parallel: bool = True,
) -> dict[str, SubagentResult]:
    """Spawn two subagents in TRUE PARALLEL via asyncio.gather().

    Both agents launch simultaneously — no serial waiting.
    Target: both complete in max(slowest, fastest) instead of sum(slowest, fastest).

    Args:
        explore_prompt: Task for the first subagent.
        verify_prompt: Task for the second subagent (independent of explore).
        explore_model: Model for Explore (default: v4-flash for speed).
        verify_model: Model for Verify (default: v4-pro for accuracy).
        explore_type: Agent type for first subagent.
        verify_type: Agent type for second subagent.
        parallel: If True (default), both run simultaneously via asyncio.
                  If False, serial fallback (legacy mode).

    Returns:
        {"explore": SubagentResult, "verify": SubagentResult}
    """
    if not parallel:
        # Serial fallback for backward compatibility
        explore = spawn_subagent(
            type=explore_type,
            prompt=explore_prompt,
            tools_list=["read", "bash", "grep", "find", "ls"],
            model=explore_model,
        )
        verify = spawn_subagent(
            type=verify_type,
            prompt=verify_prompt,
            model=verify_model,
        )
        return {"explore": explore, "verify": verify}

    # True parallel: both subprocesses launch simultaneously
    async def _run_parallel():
        explore_task = _spawn_async(
            type=explore_type,
            prompt=explore_prompt,
            tools_list=["read", "bash", "grep", "find", "ls"],
            model=explore_model,
        )
        verify_task = _spawn_async(
            type=verify_type,
            prompt=verify_prompt,
            model=verify_model,
        )
        explore_result, verify_result = await asyncio.gather(
            explore_task, verify_task
        )
        return explore_result, verify_result

    explore, verify = asyncio.run(_run_parallel())
    return {"explore": explore, "verify": verify}


def spawn_multi(
    tasks: list[dict],
    parallel: bool = True,
) -> list[SubagentResult]:
    """Spawn N subagents in TRUE PARALLEL via asyncio.gather().

    All agents launch simultaneously — no serial waiting.
    Total time = max(all tasks), not sum(all tasks).

    Args:
        tasks: List of dicts, each with:
            - type: str (e.g. "Explore", "general-purpose")
            - prompt: str (task description)
            - model: Optional[str] (override; falls back to TYPE_MODEL_MAP)
            - tools_list: Optional[list[str]]
        parallel: If True (default), all run simultaneously via asyncio.
                  If False, serial fallback.

    Returns:
        List[SubagentResult] in same order as tasks input.
    """
    if not parallel:
        # Serial fallback
        results = []
        for task in tasks:
            results.append(spawn_subagent(
                type=task.get("type", "Explore"),
                prompt=task["prompt"],
                tools_list=task.get("tools_list"),
                model=task.get("model"),
            ))
        return results

    # True N-way parallel
    async def _run_all():
        async_tasks = []
        for task in tasks:
            async_tasks.append(_spawn_async(
                type=task.get("type", "Explore"),
                prompt=task["prompt"],
                tools_list=task.get("tools_list"),
                model=task.get("model"),
            ))
        return await asyncio.gather(*async_tasks)

    return list(asyncio.run(_run_all()))


# ── CLI entry point ─────────────────────────────────────────
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Pi Subagent Bridge")
    parser.add_argument("--type", default="Explore", help="Subagent type")
    parser.add_argument("--prompt", required=True, help="Task prompt")
    parser.add_argument("--model", help="Override model")
    parser.add_argument("--dual", action="store_true", help="Run Explore+Verify dual mode")
    parser.add_argument("--verify-prompt", help="Verification prompt (dual mode)")
    args = parser.parse_args()

    if args.dual:
        if not args.verify_prompt:
            print("--verify-prompt required in dual mode", file=sys.stderr)
            sys.exit(2)
        results = spawn_dual(args.prompt, args.verify_prompt)
        print(json.dumps({
            "explore": {
                "success": results["explore"].success,
                "stdout": results["explore"].stdout,
                "exit_code": results["explore"].exit_code,
            },
            "verify": {
                "success": results["verify"].success,
                "stdout": results["verify"].stdout,
                "exit_code": results["verify"].exit_code,
            },
        }, indent=2))
    else:
        result = spawn_subagent(type=args.type, prompt=args.prompt, model=args.model)
        print(json.dumps({
            "success": result.success,
            "type": result.type,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "exit_code": result.exit_code,
            "model": result.model,
        }, indent=2))
