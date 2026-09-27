"""WS 线程 loop 收尾（2026-09-28）用例。

背景：``lark_oapi`` ``ws.Client.start()`` 返回后，其内部 ``Client._ping_loop()``
任务仍 pending；该 loop 从未 close ⇒ 解释器关闭期任务 GC 触发
"Task was destroyed but it is pending!"，其 ``__del__`` 又对已关 loop 调
``call_soon`` ⇒ ``RuntimeError: Event loop is closed`` ⇒ asyncio 异常处理器
去写日志 ⇒ 与脱敏惰性 import 叠加成 23 条级联 Traceback。
``_drain_ws_loop`` 在本线程内 cancel + 有界等待 + close。
"""
import asyncio
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from gateway.platforms.feishu_adapter import FeishuAdapter


def _mk_loop_with_pending():
    loop = asyncio.new_event_loop()

    async def _forever():
        await asyncio.sleep(30)

    task = loop.create_task(_forever())
    loop.run_until_complete(asyncio.sleep(0))
    return loop, task


def test_pending_task_is_cancelled_and_loop_closed():
    """正控：drain 后任务 done + loop closed（不再挂到解释器关闭期）。"""
    loop, task = _mk_loop_with_pending()
    assert not task.done()
    FeishuAdapter._drain_ws_loop(loop)
    assert task.done()
    assert loop.is_closed()


def test_without_drain_task_stays_pending():
    """负控（受控差分对）：不 drain ⇒ 任务仍 pending、loop 未关 —— 旧码形态。"""
    loop, task = _mk_loop_with_pending()
    assert not task.done() and not loop.is_closed()
    task.cancel()
    loop.run_until_complete(asyncio.gather(task, return_exceptions=True))
    loop.close()


def test_already_closed_loop_is_noop():
    loop = asyncio.new_event_loop()
    loop.close()
    FeishuAdapter._drain_ws_loop(loop)


def test_loop_without_tasks_is_closed():
    loop = asyncio.new_event_loop()
    FeishuAdapter._drain_ws_loop(loop)
    assert loop.is_closed()
