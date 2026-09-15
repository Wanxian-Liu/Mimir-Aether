"""F2 — the gateway stop path must not join a never-returning thread (2026-09-15).

Incident: **every** gateway stop was a hard kill.  ``journalctl --user -u
mimiraether.service`` showed, in order::

    Stopping mimiraether.service...
    [Feishu] WS thread did not exit within 5s timeout
    stop-sigterm timed out. Killing.
    Killing process <pid> with signal SIGKILL      (30s after "Stopping")
    Started mimiraether.service                    (restart)

Root cause (controlled reproduction, python 3.12.3): the lark WS long connection
ran on the *default* ThreadPoolExecutor via ``asyncio.to_thread`` and never
returns.  ``asyncio.run()`` cleanup ends with ``loop.<sd>_default_executor()`` ->
``executor.<sd>(wait=True)``, an UNBOUNDED join of that worker, so the process
just sits there until systemd's ``TimeoutStopSec=30`` SIGKILLs it.  Measured
hang: 30.04s, and instrumenting the cleanup step by step pinned the hang to the
default-executor step — the main coroutine had *already returned* before it.

Fix (F2, single idea): a never-returning blocking callable must not be scheduled
on the default executor.  ``BasePlatformAdapter._run_blocking_in_daemon_thread``
runs it in a dedicated *daemon* thread, which defeats both joiners (not in
``concurrent.futures.thread._threads_queues``; ``daemon=True`` keeps interpreter
finalization away).  Feishu (the incident) and DingTalk (identical latent
pattern, adapter currently disabled) both use it.

Probe discipline (RS17): ``test_control_old_form_reproduces_the_hang`` runs the
OLD form in a subprocess and asserts it really does hang.  Without that control,
"the new form exits fast" could just mean the probe is blind.
"""
from __future__ import annotations

import ast
import asyncio
import os
import pathlib
import subprocess
import sys
import threading
import time

import pytest

from gateway.platforms.feishu_adapter import FeishuAdapter

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
BASE = REPO_ROOT / "gateway" / "platforms" / "base.py"
FEISHU = REPO_ROOT / "gateway" / "platforms" / "feishu_adapter.py"
DINGTALK = REPO_ROOT / "gateway" / "platforms" / "dingtalk.py"

# Long-lived connections whose blocking entry point never returns.
LONG_LIVED_TARGETS = {"_blocking_lark_ws_main", "_stream_client"}

HANG_TIMEOUT = 6.0      # the old form must still be hung after this long
CLEAN_TIMEOUT = 12.0    # the new form must be done well inside this

CHILD_SRC = '''\
import asyncio
import sys
import threading

from gateway.platforms.feishu_adapter import FeishuAdapter

BLOCK = threading.Event()


class _FakeAdapter(FeishuAdapter):
    """``name`` is a read-only property on BasePlatformAdapter -> shadow it."""

    name = "feishu-f2-test"


def _make_adapter() -> FeishuAdapter:
    adapter = object.__new__(_FakeAdapter)   # bypass __init__: 1 attr suffices
    adapter._ws_thread = None
    return adapter


async def _scenario(mode: str) -> None:
    adapter = _make_adapter()
    if mode == "daemon":
        task = asyncio.ensure_future(
            adapter._run_blocking_in_daemon_thread(BLOCK.wait)  # never returns
        )
    else:  # "executor": the pre-F2 form
        task = asyncio.ensure_future(asyncio.to_thread(BLOCK.wait))
    await asyncio.sleep(0.3)
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


def main() -> None:
    asyncio.run(_scenario(sys.argv[1]))
    print("F2_ASYNCIO_RUN_RETURNED", flush=True)


main()
'''


def _run_child(tmp_path: pathlib.Path, mode: str, timeout: float):
    script = tmp_path / "f2_child.py"
    script.write_text(CHILD_SRC, encoding="utf-8")
    env = dict(os.environ)
    env["PYTHONPATH"] = str(REPO_ROOT) + os.pathsep + env.get("PYTHONPATH", "")
    return subprocess.run(
        [sys.executable, str(script), mode],
        cwd=str(REPO_ROOT), capture_output=True, text=True, timeout=timeout, env=env,
    )


def _callee_name(func: ast.AST) -> str:
    if isinstance(func, ast.Attribute):
        return func.attr
    if isinstance(func, ast.Name):
        return func.id
    return ""


def _fake_adapter() -> FeishuAdapter:
    class _Fake(FeishuAdapter):
        name = "feishu-f2-unit"

    adapter = object.__new__(_Fake)
    adapter._ws_thread = None
    return adapter


# ------------------------------------------------------- structural ban (F2-2)
@pytest.mark.parametrize("path", [FEISHU, DINGTALK], ids=["feishu", "dingtalk"])
def test_long_lived_callable_is_never_scheduled_on_default_executor(path) -> None:
    """to_thread()/run_in_executor() must not receive a never-returning target."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    offenders: list[int] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if _callee_name(node.func) not in {"to_thread", "run_in_executor"}:
            continue
        for cand in list(node.args) + [kw.value for kw in node.keywords]:
            names = set()
            if isinstance(cand, ast.Attribute):
                names.add(cand.attr)
                if isinstance(cand.value, ast.Attribute):
                    names.add(cand.value.attr)
            if names & LONG_LIVED_TARGETS:
                offenders.append(node.lineno)
    assert offenders == [], (
        f"{path.name}: a never-returning callable is scheduled on the default "
        f"executor (lines {offenders}); the process stop will hang until SIGKILL"
    )


def test_call_sites_use_the_daemon_thread_helper() -> None:
    assert "def _run_blocking_in_daemon_thread(self" in BASE.read_text(encoding="utf-8")
    assert "daemon=True" in BASE.read_text(encoding="utf-8")
    for path in (FEISHU, DINGTALK):
        src = path.read_text(encoding="utf-8")
        assert "await self._run_blocking_in_daemon_thread(" in src, path.name


# ------------------------------------------------------- semantics preserved
def test_worker_exception_reaches_the_awaiter() -> None:
    """Callers rely on this for reconnect / circuit-breaker logic."""
    adapter = _fake_adapter()

    def boom() -> None:
        raise RuntimeError("stream client exploded")

    async def scenario() -> None:
        with pytest.raises(RuntimeError, match="stream client exploded"):
            await adapter._run_blocking_in_daemon_thread(boom)

    asyncio.run(scenario())


def test_cancelling_the_awaiting_task_propagates_cancelled_error() -> None:
    adapter = _fake_adapter()
    block = threading.Event()

    async def scenario() -> None:
        task = asyncio.ensure_future(adapter._run_blocking_in_daemon_thread(block.wait))
        await asyncio.sleep(0.1)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(scenario())


# ------------------------------------------------- behavioral green + control
def test_asyncio_run_returns_with_the_daemon_thread(tmp_path) -> None:
    """GREEN: the process exits cleanly even though the callable never returns."""
    t0 = time.monotonic()
    done = _run_child(tmp_path, "daemon", CLEAN_TIMEOUT)
    elapsed = time.monotonic() - t0
    assert done.returncode == 0, done.stderr
    assert "F2_ASYNCIO_RUN_RETURNED" in done.stdout
    assert elapsed < 8.0, f"stop path took {elapsed:.1f}s (pre-F2 hung past 30s)"


def test_control_old_form_reproduces_the_hang(tmp_path) -> None:
    """CONTROL: the pre-F2 form must still hang -> the probe can discriminate."""
    t0 = time.monotonic()
    with pytest.raises(subprocess.TimeoutExpired):
        _run_child(tmp_path, "executor", HANG_TIMEOUT)
    assert time.monotonic() - t0 >= HANG_TIMEOUT * 0.8
