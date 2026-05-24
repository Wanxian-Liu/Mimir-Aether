"""STAB-02: persistent async bridge — no per-turn loop close in gateway workers."""

from __future__ import annotations

import asyncio
import concurrent.futures

from agent.async_bridge import get_worker_loop, run_async


def test_run_async_worker_thread_reuses_persistent_loop():
    loop_ids: list[int] = []

    async def _noop():
        return asyncio.get_running_loop()

    def _worker():
        loop_ids.append(id(run_async(_noop())))
        loop_ids.append(id(run_async(_noop())))
        return id(get_worker_loop())

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        worker_loop_id = pool.submit(_worker).result(timeout=5)

    assert len(loop_ids) == 2
    assert loop_ids[0] == loop_ids[1] == worker_loop_id


def test_run_async_worker_loop_stays_open_after_coroutine():
    closed_flags: list[bool] = []

    async def _noop():
        return None

    def _worker():
        run_async(_noop())
        loop = get_worker_loop()
        closed_flags.append(loop.is_closed())
        return loop.is_closed()

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        assert pool.submit(_worker).result(timeout=5) is False
    assert closed_flags == [False]


def test_run_agent_run_conversation_uses_run_async(monkeypatch):
    from agent.async_bridge import run_async as real_run_async
    from run_agent import AIAgent

    calls: list[str] = []

    async def fake_turn(*_a, **_k):
        return "ok"

    fake_agent = type("FakeAgent", (), {"run_conversation": fake_turn})()

    def _track_run_async(coro):
        calls.append("run_async")
        return real_run_async(coro)

    monkeypatch.setattr("agent.async_bridge.run_async", _track_run_async)

    agent = AIAgent()
    monkeypatch.setattr(agent, "_get_real_agent", lambda: fake_agent)
    result = agent.run_conversation("hi")

    assert result["final_response"] == "ok"
    assert calls == ["run_async"]
