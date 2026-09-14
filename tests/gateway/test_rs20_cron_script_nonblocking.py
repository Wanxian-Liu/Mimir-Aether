"""RS20 — cron script execution must not block the gateway event loop.

Incident (2026-09-15): cron job 6d82dd753060 (`mech_checks_cron.py`) ran a slow
script.  gateway/cron_mixin.py waited for it with a *synchronous*
`subprocess.run(...)` ON the event loop thread, so the whole gateway froze:
HTTP /health -> 000, Feishu replies stalled, zero log output.  py-spy showed

    MainThread: select <- communicate <- run(subprocess) <- execute_cron_job

Probe discipline (RS17): the heartbeat metric is itself validated by a CONTROL
test that runs the OLD inline blocking pattern and must observe a long stall.
Without that control, "no stall observed" could just mean the probe is blind.
"""
from __future__ import annotations

import ast
import asyncio
import pathlib
import subprocess
import time
from types import SimpleNamespace

import gateway.cron_mixin as cron_mixin
from gateway.cron_mixin import CronMixin

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
CRON_MIXIN_SRC = REPO_ROOT / "gateway" / "cron_mixin.py"

HEARTBEAT_INTERVAL = 0.02
STALL_THRESHOLD = 1.0  # seconds of loop starvation that counts as "frozen"


# --------------------------------------------------------------------- harness
class _FakeEntry:
    session_key = "rs20:test"
    session_id = "rs20-test-session"


class _FakeStore:
    def get_or_create_session(self, source):
        return _FakeEntry()


class _Host(CronMixin):
    """Minimal host standing in for GatewayRunner."""

    def __init__(self) -> None:
        self.config = SimpleNamespace()
        self.session_store = _FakeStore()
        self.adapters: dict = {}
        self._running_agents: dict = {}
        self._background_tasks: set = set()


def _install_stubs(monkeypatch, tmp_home: pathlib.Path, recorded: list):
    """Neutralise everything execute_cron_job touches except the script path."""
    import gateway.session as gw_session
    import gateway.session_context as gw_session_ctx
    import cron.jobs as cron_jobs

    (tmp_home / "scripts").mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(cron_mixin, "get_hermes_home", lambda: str(tmp_home))
    monkeypatch.setattr(gw_session, "build_session_context", lambda *a, **k: {})
    monkeypatch.setattr(gw_session, "build_session_context_prompt", lambda *a, **k: "")
    monkeypatch.setattr(gw_session_ctx, "set_session_vars", lambda **k: [])
    monkeypatch.setattr(gw_session_ctx, "clear_session_vars", lambda tokens: None)
    monkeypatch.setattr(
        cron_jobs,
        "mark_job_run",
        lambda job_id, status, error=None: recorded.append((job_id, status, error)),
    )


def _write_script(tmp_home: pathlib.Path, body: str, name: str = "rs20_sleeper.sh") -> str:
    path = tmp_home / "scripts" / name
    path.write_text("#!/bin/bash\nset -u\n" + body, encoding="utf-8")
    path.chmod(0o755)
    return name


async def _with_heartbeat(coro, guard: float = 60.0):
    """Run *coro* while sampling event-loop scheduling latency.

    Returns (max_gap_seconds, elapsed_seconds).  A gap far above
    HEARTBEAT_INTERVAL means the loop was starved (someone blocked it).
    """
    stop = asyncio.Event()
    gaps: list = []

    async def _beat() -> None:
        last = time.perf_counter()
        while not stop.is_set():
            await asyncio.sleep(HEARTBEAT_INTERVAL)
            now = time.perf_counter()
            gaps.append(now - last)
            last = now

    beat = asyncio.create_task(_beat())
    # Let the beat task actually start and record its baseline BEFORE the code
    # under test gets the loop; otherwise a fully blocking call would starve it
    # before its first sample and `gaps` would be empty => a false "no stall".
    await asyncio.sleep(0)
    t0 = time.perf_counter()
    try:
        await asyncio.wait_for(coro, timeout=guard)
    finally:
        elapsed = time.perf_counter() - t0
        stop.set()
        await beat
    return (max(gaps) if gaps else 0.0), elapsed


def _job(script: str, job_id: str = "rs20-test-job") -> dict:
    return {
        "id": job_id,
        "name": "rs20 test",
        "script": script,
        "deliver": "local",
        "prompt": "",
    }


# ------------------------------------------- 1. control: probe has power
def test_control_old_inline_subprocess_blocks_the_loop(tmp_path, monkeypatch):
    """If this passes, the heartbeat probe can actually detect blocking."""
    tmp_home = tmp_path / "home"
    _install_stubs(monkeypatch, tmp_home, [])
    script = tmp_home / "scripts" / "rs20_sleeper.sh"
    script.write_text("#!/bin/bash\nsleep 2.5\n", encoding="utf-8")
    script.chmod(0o755)

    async def _old_pattern():
        # exactly what cron_mixin.py used to do, on the loop thread
        return subprocess.run(
            ["/bin/bash", str(script)], capture_output=True, text=True, timeout=30
        )

    gap, elapsed = asyncio.run(_with_heartbeat(_old_pattern()))
    assert elapsed >= 2.0, f"script did not actually sleep? elapsed={elapsed:.2f}"
    assert gap >= STALL_THRESHOLD, (
        "control failed: blocking call did NOT starve the loop "
        f"(max_gap={gap:.3f}s) - heartbeat probe is blind"
    )


# ------------------------------------------- 2. RS20: real path stays alive
def test_execute_cron_job_does_not_block_the_loop(tmp_path, monkeypatch):
    tmp_home = tmp_path / "home"
    recorded: list = []
    _install_stubs(monkeypatch, tmp_home, recorded)
    marker = tmp_path / "ran.txt"
    script = _write_script(tmp_home, f'echo ran > "{marker}"\nsleep 2.5\n')

    async def _call():
        return await _Host().execute_cron_job(_job(script))

    gap, elapsed = asyncio.run(_with_heartbeat(_call()))

    assert marker.exists(), "script never ran - assertions below would be vacuous"
    assert elapsed >= 2.0, f"did not actually wait for the script (elapsed={elapsed:.2f}s)"
    assert gap < STALL_THRESHOLD, (
        f"event loop was starved for {gap:.3f}s while a cron script ran "
        "=> gateway frozen (HTTP 000, Feishu replies stalled)"
    )
    assert ("rs20-test-job", "ok", None) in recorded, recorded


# ------------------------------------------- 3. timeout kills the whole tree
def test_timeout_kills_process_tree_and_records_timeout(tmp_path, monkeypatch):
    tmp_home = tmp_path / "home"
    recorded: list = []
    _install_stubs(monkeypatch, tmp_home, recorded)
    monkeypatch.setattr(cron_mixin, "_CRON_SCRIPT_TIMEOUT_S", 1)

    pid_file = tmp_path / "pids.txt"
    script = _write_script(
        tmp_home,
        f'echo "$$" > "{pid_file}"\nsleep 60 &\necho "$!" >> "{pid_file}"\nwait\n',
    )

    async def _call():
        # The timeout path sets final_text="(timeout)" which then enters job
        # DELIVERY — that needs the full GatewayRunner (delivery_router) and is
        # outside this test's scope.  The facts under test (status=timeout, the
        # process tree dying, the loop staying responsive) all happen before it.
        try:
            return await _Host().execute_cron_job(_job(script))
        except Exception:
            return None

    gap, elapsed = asyncio.run(_with_heartbeat(_call(), guard=30))

    pids = [int(x) for x in pid_file.read_text().split() if x.strip().isdigit()]
    assert len(pids) == 2, f"expected wrapper+grandchild pids, got {pids}"
    assert elapsed < 20, f"timeout not enforced (elapsed={elapsed:.1f}s)"
    assert gap < STALL_THRESHOLD, f"loop starved during timeout path ({gap:.3f}s)"
    assert any(s == "timeout" for _, s, _ in recorded), recorded

    deadline = time.time() + 5
    alive = set(pids)
    while alive and time.time() < deadline:
        alive = {p for p in alive if pathlib.Path(f"/proc/{p}").exists()}
        time.sleep(0.1)
    assert not alive, f"process tree survived the kill: {sorted(alive)} (pids={pids})"


# ------------------------------------------- 4. source guard (no regression)
def test_source_has_no_bare_subprocess_run_in_cron_mixin():
    src = CRON_MIXIN_SRC.read_text(encoding="utf-8")
    tree = ast.parse(src)

    offenders = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        fn = node.func
        if (
            isinstance(fn, ast.Attribute)
            and fn.attr == "run"
            and isinstance(fn.value, ast.Name)
            and fn.value.id == "subprocess"
        ):
            offenders.append(getattr(node, "lineno", -1))
    assert not offenders, (
        f"bare subprocess.run() found at lines {offenders} in gateway/cron_mixin.py - "
        "a synchronous wait in the async cron path freezes the gateway"
    )

    assert "await asyncio.to_thread(_run_cron_script)" in src
    assert "start_new_session=True" in src
    assert "os.killpg(" in src
    assert "timeout=600" not in src, "old 600s cap resurfaced"
