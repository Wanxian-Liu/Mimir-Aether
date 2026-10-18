"""F5 止血：同一会话的 transcript 重写必须单飞（防同 collection 双写）。

背景（2026-10-19 盘上实证）：
    `rewrite_transcript_off_loop` 用 `asyncio.to_thread` + `asyncio.wait_for`。
    `wait_for` 超时**只停止等待**——Python 线程不可取消，worker 继续写 chroma。
    卫生层每轮（约 30 分钟）再起一个新 worker，两个 writer 同时写同一 collection
    ⇒ HNSW 段与 sqlite 不同步（段 00:37 / 库 02:18）⇒ `Collection.count()` SEGV
    （02:16/16:55/17:33/18:10 连崩 4 次）⇒ 旧库被改名止血。

本测试锁住三件事：
    R1 同会话并发 ⇒ 第二个被 SKIP（不起新 worker）
    R2 不同会话 ⇒ 互不阻塞（负控，防过度串行化）
    R3 超时不释放闸（worker 仍在跑）；worker 真正结束后自动恢复

以及一条源码闸：
    R4 noop 路径不得触发索引重写（noop 压缩一条没删却烧 31~41s 的元凶）
"""
from __future__ import annotations

import asyncio
import pathlib
import threading
import time

from gateway.session import rewrite_transcript_off_loop

REPO = pathlib.Path(__file__).resolve().parents[2]
ROUTE_SRC = REPO / "gateway/router/agent_route_mixin.py"


class SlowStore:
    """记录实际起了几个 worker，并让它们慢下来以便制造并发窗口。"""

    def __init__(self, delay: float = 0.8) -> None:
        self.delay = delay
        self.calls = 0
        self._lock = threading.Lock()

    def rewrite_transcript(self, session_id, messages, skip_db):  # noqa: ANN001
        with self._lock:
            self.calls += 1
        time.sleep(self.delay)
        return True


# ── R1 同会话单飞 ────────────────────────────────────────────────────────


def test_same_session_concurrent_rewrite_is_skipped():
    store = SlowStore(0.8)

    async def main():
        first = asyncio.create_task(
            rewrite_transcript_off_loop(store, "S1", [{"role": "user"}], timeout_s=5.0)
        )
        await asyncio.sleep(0.15)  # 让第一个真正进入 worker
        second = await rewrite_transcript_off_loop(
            store, "S1", [{"role": "user"}], timeout_s=5.0
        )
        return await first, second

    r1, r2 = asyncio.run(main())
    assert r1 is True, "第一个应正常完成"
    assert r2 is False, "第二个应被单飞闸跳过"
    assert store.calls == 1, f"同会话只允许 1 个 worker，实测 {store.calls}"


# ── R2 负控：不同会话不互相阻塞 ─────────────────────────────────────────


def test_different_sessions_are_not_serialized():
    store = SlowStore(0.5)

    async def main():
        a = asyncio.create_task(
            rewrite_transcript_off_loop(store, "A", [], timeout_s=5.0)
        )
        await asyncio.sleep(0.1)
        rb = await rewrite_transcript_off_loop(store, "B", [], timeout_s=5.0)
        return await a, rb

    ra, rb = asyncio.run(main())
    assert ra is True and rb is True, "不同会话必须都能跑（防过度串行化）"
    assert store.calls == 2


# ── R3 超时不释放闸；worker 结束后恢复 ──────────────────────────────────


def test_timeout_keeps_guard_until_worker_really_exits():
    store = SlowStore(1.2)

    async def main():
        r1 = await rewrite_transcript_off_loop(store, "S2", [], timeout_s=0.2)
        r2 = await rewrite_transcript_off_loop(store, "S2", [], timeout_s=0.2)
        await asyncio.sleep(1.4)  # 等第一个 worker 真正退出
        r3 = await rewrite_transcript_off_loop(store, "S2", [], timeout_s=5.0)
        return r1, r2, r3

    r1, r2, r3 = asyncio.run(main())
    assert r1 is False, "超时应报 False"
    assert r2 is False, "超时后 worker 仍在跑 ⇒ 必须继续挡（否则就是双写）"
    assert r3 is True, "worker 退出后闸必须自动释放（否则永久卡死）"
    assert store.calls == 2, f"第2次不得起新 worker，实测 {store.calls}"


# ── R4 源码闸：noop 不得触发索引重写 ────────────────────────────────────


def test_noop_path_does_not_trigger_index_rewrite():
    src = ROUTE_SRC.read_text(encoding="utf-8")
    idx_noop_guard = src.find("if _new_count >= len(_hyg_msgs):")
    idx_rewrite = src.find("await rewrite_transcript_off_loop(")
    assert idx_noop_guard > 0, "noop 判据必须存在"
    assert idx_rewrite > 0, "索引重写调用必须存在"
    assert idx_rewrite > idx_noop_guard, (
        "索引重写必须排在 noop 判定**之后**——否则 noop（一条没删）也触发全量重同步"
    )
