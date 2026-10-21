"""RL-20261020-094: cross-process write lock for the chroma session index.

Two-way by construction: the same harness runs once with the real lock and once
with the guard monkeypatched to a no-op (negative control). If the detector
cannot see overlap in the no-op arm, the green arm proves nothing.

Child mode: this file re-invokes itself (``sys.executable <this file> hold A 0.25``)
so the "other process" is a real OS process, not a thread.
"""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import threading
import time
from contextlib import nullcontext
from pathlib import Path
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import tools.chroma_session_indexer as csi  # noqa: E402


# --------------------------------------------------------------------------- #
# child mode (real OS process)
# --------------------------------------------------------------------------- #
def _hold(tag: str, seconds: float) -> None:
    with csi.chroma_write_lock():
        t_held = time.time()
        print("held", flush=True)
        time.sleep(seconds)
        t_end = time.time()
    print(json.dumps({"tag": tag, "t_held": t_held, "t_end": t_end}), flush=True)


def _run_child() -> int:
    mode = sys.argv[1]
    if mode == "hold":
        _hold(sys.argv[2], float(sys.argv[3]))
        return 0
    if mode == "hold-nolock":  # negative control: guard replaced by a no-op
        csi.chroma_write_lock = lambda *a, **k: nullcontext()
        _hold(sys.argv[2], float(sys.argv[3]))
        return 0
    raise SystemExit(f"unknown child mode {mode}")


# --------------------------------------------------------------------------- #
# helpers / fixtures
# --------------------------------------------------------------------------- #
@pytest.fixture(autouse=True)
def _reset_lock_state():
    csi._WRITE_LOCK_STATE.depth = 0
    yield
    csi._WRITE_LOCK_STATE.depth = 0


def _env(tmp_path: Path, **extra: str) -> dict:
    env = dict(os.environ)
    env["MIMIR_AETHER_HOME"] = str(tmp_path)  # lock file -> <tmp>/data/
    env.pop("MIMIR_CHROMA_INCREMENTAL", None)
    env.update(extra)
    return env


def _spawn(tmp_path: Path, *args: str, **extra: str) -> subprocess.Popen:
    return subprocess.Popen(
        [sys.executable, str(Path(__file__).resolve()), *args],
        env=_env(tmp_path, **extra),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def _pair(tmp_path: Path, mode: str, hold_s: float = 0.25):
    procs = [_spawn(tmp_path, mode, tag, str(hold_s)) for tag in ("A", "B")]
    spans = []
    for proc in procs:
        out, err = proc.communicate(timeout=120)
        assert proc.returncode == 0, err
        assert out.splitlines()[0].strip() == "held", out
        spans.append(json.loads(out.splitlines()[-1]))
    return spans


def _overlap(a: dict, b: dict) -> float:
    return min(a["t_end"], b["t_end"]) - max(a["t_held"], b["t_held"])


# --------------------------------------------------------------------------- #
# tests
# --------------------------------------------------------------------------- #
def test_lock_path_is_a_sidecar_under_data_not_in_chroma_dir(monkeypatch, tmp_path):
    monkeypatch.setenv("MIMIR_AETHER_HOME", str(tmp_path))
    lock_path = csi.chroma_write_lock_path()
    assert lock_path == tmp_path / "data" / "chroma_write.lock"
    assert "chroma_sessions" not in str(lock_path)


def test_two_processes_do_not_write_concurrently(tmp_path):
    a, b = _pair(tmp_path, "hold")
    assert _overlap(a, b) <= 0.0, (a, b)


def test_negative_control_harness_can_see_overlap(tmp_path):
    """Same harness, guard disabled => overlap MUST appear (detector is alive)."""
    a, b = _pair(tmp_path, "hold-nolock")
    assert _overlap(a, b) > 0.1, (a, b)


def test_lock_timeout_is_bounded_and_raises(monkeypatch, tmp_path):
    monkeypatch.setenv("MIMIR_AETHER_HOME", str(tmp_path))
    holder = _spawn(tmp_path, "hold", "H", "10")
    try:
        assert holder.stdout.readline().strip() == "held"
        monkeypatch.setenv("MIMIR_CHROMA_WRITE_LOCK_TIMEOUT_S", "0.3")
        t0 = time.time()
        with pytest.raises(csi.ChromaWriteLockTimeout):
            with csi.chroma_write_lock():
                pass
        waited = time.time() - t0
        assert 0.25 <= waited < 3.0, waited
        assert csi._WRITE_LOCK_STATE.depth == 0
    finally:
        holder.kill()
        holder.communicate(timeout=30)


def test_sigkill_holder_releases_the_lock(monkeypatch, tmp_path):
    monkeypatch.setenv("MIMIR_AETHER_HOME", str(tmp_path))
    holder = _spawn(tmp_path, "hold", "H", "30")
    assert holder.stdout.readline().strip() == "held"
    holder.send_signal(signal.SIGKILL)
    holder.communicate(timeout=30)

    monkeypatch.setenv("MIMIR_CHROMA_WRITE_LOCK_TIMEOUT_S", "2")
    t0 = time.time()
    with csi.chroma_write_lock():
        pass
    assert time.time() - t0 < 1.5


def test_same_thread_reentrant(monkeypatch, tmp_path):
    """Re-entry stays free under the B3 deadline: RLock returns True at once
    when the current thread already owns it, so a near-zero budget must not
    turn nesting into a timeout."""
    monkeypatch.setenv("MIMIR_AETHER_HOME", str(tmp_path))
    monkeypatch.setenv("MIMIR_CHROMA_WRITE_LOCK_TIMEOUT_S", "0.001")
    t0 = time.monotonic()
    with csi.chroma_write_lock():
        with csi.chroma_write_lock():
            assert csi._WRITE_LOCK_STATE.depth == 2
        assert csi._WRITE_LOCK_STATE.depth == 1
    assert csi._WRITE_LOCK_STATE.depth == 0
    assert time.monotonic() - t0 < 0.5


def test_two_threads_in_one_process_serialise(monkeypatch, tmp_path):
    monkeypatch.setenv("MIMIR_AETHER_HOME", str(tmp_path))
    spans = []

    def work(tag):
        with csi.chroma_write_lock():
            t0 = time.time()
            time.sleep(0.2)
            spans.append({"tag": tag, "t_held": t0, "t_end": time.time()})

    threads = [threading.Thread(target=work, args=(t,)) for t in ("A", "B")]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert _overlap(spans[0], spans[1]) <= 0.0, spans


def test_upsert_path_takes_the_lock(monkeypatch, tmp_path):
    monkeypatch.setenv("MIMIR_AETHER_HOME", str(tmp_path))
    calls = []

    def fake_lock():
        calls.append(1)
        return nullcontext()

    monkeypatch.setattr(csi, "chroma_write_lock", fake_lock)
    collection = MagicMock()
    msg = csi.IndexedMessage(
        message_id=1, session_id="s", role="user", content="hello", source="t", timestamp=0.0
    )
    assert csi._upsert_batch(collection, [msg]) == 1
    assert collection.upsert.called
    assert len(calls) == 1


def test_delete_path_takes_the_lock(monkeypatch, tmp_path):
    monkeypatch.setenv("MIMIR_AETHER_HOME", str(tmp_path))
    calls = []
    monkeypatch.setattr(csi, "chroma_available", lambda: True)
    monkeypatch.setattr(
        csi, "chroma_write_lock", lambda: (calls.append(1), nullcontext())[1]
    )
    collection = MagicMock()
    csi.delete_session_chroma_documents("s1", collection=collection)
    assert collection.delete.called
    assert len(calls) == 1


def test_delete_path_blocks_while_lock_held(monkeypatch, tmp_path):
    """Behaviour, not logging: while another *process* holds the write lock, the
    delete path (``_delete_stale_session_docs``) must actually wait on it.

    Static coverage (the AST gate) can only see that a ``with`` wraps the call;
    it cannot see that the guard is really taken. This asserts the elapsed lower
    bound of the blocked caller, and the child proves the hold was real.
    """
    monkeypatch.setenv("MIMIR_AETHER_HOME", str(tmp_path))
    monkeypatch.delenv("MIMIR_CHROMA_INCREMENTAL", raising=False)
    holder = _spawn(tmp_path, "hold", "H", "2")
    try:
        assert holder.stdout.readline().strip() == "held"
        from tools import session_search_indexer as ssi

        collection = MagicMock()
        collection.get.return_value = {"ids": ["d1", "d2"]}
        monkeypatch.setattr(csi, "_get_incremental_collection", lambda: collection)
        monkeypatch.setattr(csi, "get_chroma_collection", lambda: collection)
        t0 = time.time()
        out = ssi._delete_stale_session_docs("s1", ["d1", "d2"])
        waited = time.time() - t0
        assert out.get("deleted") == 2, out
        assert collection.delete.called
        assert waited >= 1.5, waited
    finally:
        holder.kill()
        holder.communicate(timeout=30)


def test_deleted_lock_file_is_reopened(monkeypatch, tmp_path):
    """Documented residual hole: unlinking the lock file lets a *new* inode be
    locked, so one round of mutual exclusion can be lost. We must not crash and
    must re-open on the next acquire (depth bookkeeping stays sane)."""
    monkeypatch.setenv("MIMIR_AETHER_HOME", str(tmp_path))
    lock_path = csi.chroma_write_lock_path()
    with csi.chroma_write_lock():
        first_nonce = csi._WRITE_LOCK_STATE.nonce
        lock_path.unlink()
    assert csi._WRITE_LOCK_STATE.depth == 0
    with csi.chroma_write_lock():
        second_nonce = csi._WRITE_LOCK_STATE.nonce
    assert lock_path.exists()
    # our fd was locking an unlinked inode -> the nonce check must re-open
    assert first_nonce != second_nonce
    # and the visible file now carries the live holder's token
    assert lock_path.read_text(encoding="utf-8").strip() == second_nonce


# --------------------------------------------------------------------------- #
# RL-20261020-094 B3: the *in-process* wait must also be bounded
# --------------------------------------------------------------------------- #
def test_in_process_wait_is_bounded(monkeypatch, tmp_path):
    """Another *thread* in this process holding the RLock must not let a waiter
    silently overrun ``MIMIR_CHROMA_WRITE_LOCK_TIMEOUT_S``.

    Before B3 the waiter used a bare ``RLock.acquire()``: with a 0.3s budget and
    a 2.5s holder it returned after ~1.8s with the lock in hand -- budget
    ignored, nothing logged, caller past its own deadline. Red before, green now.
    """
    monkeypatch.setenv("MIMIR_AETHER_HOME", str(tmp_path))
    monkeypatch.setenv("MIMIR_CHROMA_WRITE_LOCK_TIMEOUT_S", "0.3")
    held = threading.Event()
    release = threading.Event()
    depth_while_held = []

    def hold() -> None:
        with csi.chroma_write_lock():
            depth_while_held.append(csi._WRITE_LOCK_STATE.depth)
            held.set()                 # prove we really own the guard
            release.wait(timeout=10.0)

    holder = threading.Thread(target=hold, daemon=True)
    holder.start()
    try:
        assert held.wait(timeout=5.0), "holder thread never took the lock"
        assert depth_while_held == [1], depth_while_held

        t0 = time.monotonic()
        with pytest.raises(csi.ChromaWriteLockTimeout) as excinfo:
            with csi.chroma_write_lock():
                pytest.fail("waiter must not enter the guard past its deadline")
        elapsed = time.monotonic() - t0

        assert 0.2 <= elapsed <= 1.0, elapsed
        assert "0.3s" in str(excinfo.value), str(excinfo.value)
        assert "same-process contention" in str(excinfo.value), str(excinfo.value)
        # the refused waiter never took the lock: no depth bump, no release owed
        assert csi._WRITE_LOCK_STATE.depth == 1, csi._WRITE_LOCK_STATE.depth
    finally:
        release.set()
        holder.join(timeout=10.0)
    assert not holder.is_alive()
    assert csi._WRITE_LOCK_STATE.depth == 0

    # once the holder is gone the same caller gets in, and depth still unwinds
    t1 = time.monotonic()
    with csi.chroma_write_lock():
        assert csi._WRITE_LOCK_STATE.depth == 1
    assert time.monotonic() - t1 < 1.0
    assert csi._WRITE_LOCK_STATE.depth == 0


# --------------------------------------------------------------------------- #
# RL-20261020-094 B4: a timeout must name the holder, not just "not acquired"
# --------------------------------------------------------------------------- #
def test_timeout_message_names_holder(monkeypatch, tmp_path):
    """Cross-process timeout: the message must carry the *holder's* pid, its
    liveness, and the in-band token -- that is the one datum a responder needs
    and cannot guess from the time window.

    The holder here is a real OS process (``_spawn`` re-invokes this file), so
    the pid in the message must equal that child's pid, not ours.
    """
    monkeypatch.setenv("MIMIR_AETHER_HOME", str(tmp_path))
    holder = _spawn(tmp_path, "hold", "H", "3")
    try:
        assert holder.stdout.readline().strip() == "held"
        monkeypatch.setenv("MIMIR_CHROMA_WRITE_LOCK_TIMEOUT_S", "0.3")
        with pytest.raises(csi.ChromaWriteLockTimeout) as excinfo:
            with csi.chroma_write_lock():
                pytest.fail("must not acquire while a child process holds the lock")
    finally:
        holder.kill()
        holder.communicate(timeout=30)

    msg = str(excinfo.value)
    assert "holder=" in msg, msg
    assert str(holder.pid) in msg, (holder.pid, msg)
    assert "alive" in msg, msg
    assert f"pid={holder.pid} (alive)" in msg, msg


def test_in_process_timeout_names_thread_not_pid(monkeypatch, tmp_path):
    """Same-process contention is a *thread*, not another pid -- naming it as a
    pid would send the responder hunting a process that does not exist."""
    monkeypatch.setenv("MIMIR_AETHER_HOME", str(tmp_path))
    monkeypatch.setenv("MIMIR_CHROMA_WRITE_LOCK_TIMEOUT_S", "0.3")
    held = threading.Event()
    release = threading.Event()

    def hold() -> None:
        with csi.chroma_write_lock():
            held.set()
            release.wait(timeout=10.0)

    holder = threading.Thread(target=hold, name="chroma-holder", daemon=True)
    holder.start()
    try:
        assert held.wait(timeout=5.0), "holder thread never took the lock"
        with pytest.raises(csi.ChromaWriteLockTimeout) as excinfo:
            with csi.chroma_write_lock():
                pytest.fail("waiter must not enter the guard past its deadline")
    finally:
        release.set()
        holder.join(timeout=10.0)

    msg = str(excinfo.value)
    assert "holder=thread:" in msg, msg
    assert "holder=pid=" not in msg, msg
    assert "same process" in msg, msg


if __name__ == "__main__":
    raise SystemExit(_run_child())
