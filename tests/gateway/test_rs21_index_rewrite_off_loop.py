"""RS21 - transcript rewrite must not block the asyncio event loop.

Incident (production, 2026-09-15 09:35:34 -> 09:44:16): one gateway-layer
hygiene compression ran the full-session re-embed inline on the event-loop
thread. Result: 506 s of zero log output from every logger, /health
unresponsive, all Feishu replies stalled -- process alive but frozen.

This module is the reproduction of that incident. The control test proves the
heartbeat probe can actually detect starvation (RS17 discipline: a probe with
no working positive control is not evidence).
"""
from __future__ import annotations

import ast
import asyncio
import logging
import pathlib
import time

import pytest

from gateway.session import rewrite_offload_timeout_s, rewrite_transcript_off_loop

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
GATEWAY_DIR = REPO_ROOT / "gateway"

TICK = 0.02
WORK = 0.60
DEFAULT_TIMEOUT = 300.0

SESSION_LOGGER = "gateway.session"


class _Collector(logging.Handler):
    """Attach-to-logger collector: independent of propagate settings."""

    def __init__(self) -> None:
        super().__init__()
        self.messages = []

    def emit(self, record: logging.LogRecord) -> None:
        # getMessage() re-applies %-args: an arg-count mismatch raises here,
        # which is exactly the D1 failure class from the batch-1 review.
        self.messages.append(record.getMessage())


class _SlowStore:
    """A store whose rewrite blocks, like the real bge-m3 re-embed does."""

    def __init__(self, seconds: float) -> None:
        self.seconds = seconds
        self.calls = []

    def rewrite_transcript(self, session_id, messages, skip_db=False):
        self.calls.append((session_id, len(messages), skip_db))
        time.sleep(self.seconds)
        return True


class _BoomStore:
    def rewrite_transcript(self, session_id, messages, skip_db=False):
        raise RuntimeError("disk on fire")


async def _heartbeat(stop: asyncio.Event, gaps: list) -> None:
    loop = asyncio.get_running_loop()
    last = loop.time()
    while not stop.is_set():
        await asyncio.sleep(TICK)
        now = loop.time()
        gaps.append(now - last)
        last = now


async def _measure(awaitable):
    """Await *awaitable* while sampling event-loop starvation."""
    stop = asyncio.Event()
    gaps = []
    hb = asyncio.create_task(_heartbeat(stop, gaps))
    # Warm-up: let the heartbeat task run at least once before the measured
    # work starts. Without it a non-yielding coroutine (the control group)
    # finishes before the probe ever samples the loop, and a broken probe
    # would silently report "0.000s gap" -- i.e. indistinguishable from
    # "never blocked".
    await asyncio.sleep(TICK * 3)
    started = time.monotonic()
    result = await awaitable
    elapsed = time.monotonic() - started
    stop.set()
    await hb
    return result, elapsed, (max(gaps) if gaps else 0.0)


@pytest.fixture
def logs():
    handler = _Collector()
    logger = logging.getLogger(SESSION_LOGGER)
    old_level, old_propagate = logger.level, logger.propagate
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    try:
        yield handler
    finally:
        logger.removeHandler(handler)
        logger.setLevel(old_level)
        logger.propagate = old_propagate


def test_control_inline_call_does_starve_the_loop():
    """POSITIVE CONTROL for the whole module.

    The old inline call MUST show up as loop starvation. Without this, the
    `max_gap < threshold` assertions below would prove nothing: a broken
    probe reports "responsive" for everything.
    """
    store = _SlowStore(WORK)

    async def _inline():
        # Deliberately synchronous, inside a coroutine: this is the pre-RS21
        # production call shape.
        store.rewrite_transcript("sid", [{"role": "user", "content": "x"}])

    _, elapsed, max_gap = asyncio.run(_measure(_inline()))
    assert elapsed >= WORK * 0.9
    assert max_gap >= WORK * 0.5, (
        "control group did NOT starve the loop (max_gap=%.3fs) -> the probe "
        "cannot detect blocking, so the fix tests would be meaningless" % max_gap
    )


def test_off_loop_rewrite_keeps_loop_responsive():
    store = _SlowStore(WORK)

    async def _off():
        return await rewrite_transcript_off_loop(
            store, "sid", [{"role": "user", "content": "x"}],
            phase="hygiene-compress",
        )

    ok, elapsed, max_gap = asyncio.run(_measure(_off()))
    assert ok is True
    assert store.calls == [("sid", 1, False)]
    assert elapsed >= WORK * 0.9, "no real work happened (elapsed=%.3fs)" % elapsed
    assert max_gap < 0.20, "event loop starved for %.3fs (RS21 regression)" % max_gap


def test_timeout_is_bounded_logged_and_keeps_loop_responsive(logs):
    store = _SlowStore(5.0)

    async def _off():
        return await rewrite_transcript_off_loop(
            store, "sid", [{"role": "user"}] * 3, timeout_s=0.25,
            phase="hygiene-compress",
        )

    ok, elapsed, max_gap = asyncio.run(_measure(_off()))
    assert ok is False
    assert elapsed < 2.0, "timeout did not bound the wait (elapsed=%.2fs)" % elapsed
    assert max_gap < 0.25, "loop starved while timing out (%.3fs)" % max_gap
    text = "\n".join(logs.messages)
    assert "hygiene-compress TIMEOUT" in text
    assert "docs=3" in text
    assert "limit=0.2s" in text
    assert "event loop stayed responsive" in text


def test_begin_and_end_are_logged_with_docs_and_elapsed(logs):
    store = _SlowStore(0.05)

    async def _off():
        return await rewrite_transcript_off_loop(
            store, "sid-x", [{"role": "u"}] * 7, phase="undo",
        )

    ok, _, _ = asyncio.run(_measure(_off()))
    assert ok is True
    text = "\n".join(logs.messages)
    assert "[INDEX] undo begin sid=sid-x docs=7" in text
    assert "[INDEX] undo end sid=sid-x docs=7" in text
    assert "elapsed=" in text


def test_store_exception_is_logged_not_raised(logs):
    ok = asyncio.run(
        rewrite_transcript_off_loop(_BoomStore(), "sid", [{"role": "user"}])
    )
    assert ok is False
    text = "\n".join(logs.messages)
    assert "transcript-rewrite failed" in text
    assert "disk on fire" in text


def test_skip_db_is_forwarded():
    store = _SlowStore(0.01)

    async def _off():
        return await rewrite_transcript_off_loop(
            store, "sid", [{"role": "user"}], skip_db=True,
        )

    ok, _, _ = asyncio.run(_measure(_off()))
    assert ok is True
    assert store.calls == [("sid", 1, True)]


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("45", 45.0),
        ("0", DEFAULT_TIMEOUT),
        ("-1", DEFAULT_TIMEOUT),
        ("abc", DEFAULT_TIMEOUT),
        ("", DEFAULT_TIMEOUT),
    ],
)
def test_timeout_env_override(monkeypatch, raw, expected):
    monkeypatch.setenv("MIMIR_HYGIENE_INDEX_TIMEOUT_S", raw)
    assert rewrite_offload_timeout_s() == expected


def test_no_direct_rewrite_transcript_calls_outside_session_module():
    """Durable guard: every gateway call site must go through the offload.

    This is the "same failure class must no longer be possible" check for
    RS21 -- a new direct call would silently reintroduce the freeze.
    """
    offenders = []
    session_calls = 0
    for path in sorted(GATEWAY_DIR.rglob("*.py")):
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "rewrite_transcript"
            ):
                where = "%s:%d" % (path.relative_to(REPO_ROOT), node.lineno)
                if path.name == "session.py":
                    session_calls += 1
                else:
                    offenders.append(where)
    assert offenders == [], (
        "direct (event-loop blocking) rewrite_transcript call(s) found: %s"
        % offenders
    )
    # session.py may only host the sync primitive + its SessionManager
    # delegation; a third one would mean a new inline call path appeared.
    assert session_calls == 1, (
        "expected exactly 1 internal delegation in session.py, found %d"
        % session_calls
    )
