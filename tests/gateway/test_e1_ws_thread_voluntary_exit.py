"""E1 — 停机时 WS 线程必须**自愿退出**，且等待不得钉死事件循环（2026-09-16）。

现场（``journalctl --user -u mimiraether.service``，两次实证）::

    12:22:27 Stopping mimiraether.service...
    12:22:32 [Feishu] WS thread did not exit within 5s timeout
    12:22:44 Stopped mimiraether.service.

旧写法 ``ws_thread.join(timeout=5)`` 同时错过两个目标：

  1. **治不了线程泄漏** —— 它等的是一个永不自退的线程：``cli.start()`` 在该线程
     自己的 loop 上 ``run_until_complete`` 阻塞不返回，而 ``_ws_shutdown`` 只在
     进入前检查一次 ⇒ join **100% 等满超时**并打 WARNING。
  2. **钉死事件循环** —— 同步 join 出现在 ``async def disconnect()`` 里，把 gateway
     主循环整段阻塞（旧停机遇 17s 关停）。

两全法（四方 2026-09-16 裁决 ①②「认可」）：先 ``call_soon_threadsafe(ws_loop.stop)``
请线程**自愿退出**，再把有界 join 用 ``asyncio.to_thread`` **移出事件循环**。

探针纪律（RS17）：``test_control_old_sync_join_blocks_the_loop`` 跑**旧写法**并断言心跳
为 0 —— 没有这个控制组，「心跳照跳」也可能只说明探针是瞎的。
"""
from __future__ import annotations

import ast
import asyncio
import logging
import pathlib
import threading
import time

from gateway.platforms.feishu_adapter import FeishuAdapter

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
FEISHU = REPO_ROOT / "gateway" / "platforms" / "feishu_adapter.py"


class _Fake(FeishuAdapter):
    name = "feishu-e1-test"

    def _mark_disconnected(self) -> None:  # 本测试不碰连接状态机
        pass


def _make_adapter(ws_thread=None, ws_loop=None) -> FeishuAdapter:
    a = object.__new__(_Fake)
    a._running = True
    a._ws_shutdown = threading.Event()
    a._ws_task = None
    a._token_task = None
    a._session = None
    a._token_lock = threading.Lock()
    a._tenant_token = None
    a._ws_thread = ws_thread
    a._ws_loop = ws_loop
    return a


def _thread_running_a_real_loop(holder: dict) -> threading.Thread:
    """线程体：建自有 loop 并 run_forever（复刻 lark start() 的阻塞形态）。"""
    ready = threading.Event()

    def body() -> None:
        lp = asyncio.new_event_loop()
        asyncio.set_event_loop(lp)
        holder["loop"] = lp
        lp.call_soon(ready.set)  # 进入 run_forever 之后才 set：排除「stop 早于 run」竞态
        lp.run_forever()

    t = threading.Thread(target=body, name="fake-ws-loop", daemon=True)
    t.start()
    assert ready.wait(3.0), "自有 loop 未在 3s 内起跑"
    return t


async def _heartbeat(counter: list, stop: threading.Event, interval: float = 0.05) -> None:
    while not stop.is_set():
        counter[0] += 1
        await asyncio.sleep(interval)


# ---------------------------------------------------------------- GREEN 语义
def test_disconnect_lets_the_thread_exit_voluntarily(caplog) -> None:
    """自愿退出通路有效：线程真的结束，且不等到 5s 超时。"""
    holder: dict = {}
    t = _thread_running_a_real_loop(holder)
    a = _make_adapter(ws_thread=t, ws_loop=holder["loop"])

    with caplog.at_level(logging.WARNING):
        t0 = time.monotonic()
        asyncio.run(a.disconnect())
        elapsed = time.monotonic() - t0

    assert not t.is_alive(), "WS 线程仍未退出 ⇒ 自愿退出通路无效（join 只是白等）"
    assert elapsed < 2.0, f"disconnect 花了 {elapsed:.2f}s（自愿退出后应远小于 5s 超时）"
    assert "did not exit within 5s" not in caplog.text, "仍打了「等满超时」WARNING"
    assert a._ws_thread is None and a._ws_loop is None, "引用未清空（下次 disconnect 会误判）"


# ---------------------------------------------------------- 有界 join 不在循环里
def test_bounded_join_does_not_block_the_event_loop() -> None:
    """线程 2s 后自己结束；这 2s 内事件循环必须照样跑（心跳照跳）。

    旧写法下本测试必然失败（心跳 0）—— 它盯的正是「同步 join 钉死事件循环」。
    """
    t = threading.Thread(target=time.sleep, args=(2.0,), name="e1-stubborn", daemon=True)
    t.start()
    a = _make_adapter(ws_thread=t, ws_loop=None)  # loop=None ⇒ 无自愿退出通路

    async def scenario():
        counter = [0]
        stop = threading.Event()
        hb = asyncio.ensure_future(_heartbeat(counter, stop))
        t0 = time.monotonic()
        await a.disconnect()
        elapsed = time.monotonic() - t0
        stop.set()
        await hb
        return elapsed, counter[0]

    elapsed, ticks = asyncio.run(scenario())
    assert elapsed >= 1.5, f"没有真的等待（{elapsed:.2f}s）⇒ 探针无效"
    assert ticks >= 10, (
        f"事件循环被钉死：等待 {elapsed:.2f}s 期间只跑了 {ticks} 次心跳（应 ~{int(elapsed/0.05)}）"
    )


# ------------------------------------------------------- CONTROL（RS17 正控）
def test_control_old_sync_join_blocks_the_loop() -> None:
    """CONTROL：旧写法（同步 join）在等待期间心跳必须为 0 ⇒ 上面那个探针有鉴别力。"""
    t = threading.Thread(target=time.sleep, args=(1.5,), name="e1-control", daemon=True)
    t.start()

    async def scenario() -> int:
        counter = [0]
        stop = threading.Event()
        hb = asyncio.ensure_future(_heartbeat(counter, stop))
        t.join(timeout=1.2)  # ← 旧写法：同步 join 直接阻塞事件循环
        stop.set()
        await hb
        return counter[0]

    ticks = asyncio.run(scenario())
    assert ticks <= 1, f"旧写法下心跳应≈0（同步 join 阻塞循环），实测 {ticks} —— 探针无鉴别力"


# ------------------------------------------------------------------ 结构闸
def test_source_uses_voluntary_exit_and_off_loop_join() -> None:
    src = FEISHU.read_text(encoding="utf-8")
    assert "await asyncio.to_thread(ws_thread.join, 5)" in src, "有界 join 未移出事件循环"
    assert "ws_thread.join(timeout=5)" not in src, "E1 回退：同步 join 又回到事件循环里了"

    tree = ast.parse(src)
    fn = next(
        (n for n in ast.walk(tree)
         if isinstance(n, ast.FunctionDef) and n.name == "_request_ws_thread_exit"),
        None,
    )
    assert fn is not None, "缺少 _request_ws_thread_exit（自愿退出通路）"
    callees = {
        c.func.attr
        for c in ast.walk(fn)
        if isinstance(c, ast.Call) and isinstance(c.func, ast.Attribute)
    }
    assert "call_soon_threadsafe" in callees, "自愿退出必须走 call_soon_threadsafe（跨线程安全）"
