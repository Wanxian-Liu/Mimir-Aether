"""STAB-01: Feishu WS inbound must not block the lark worker thread."""

from __future__ import annotations

import asyncio
import json
import time
from unittest.mock import MagicMock, patch

from gateway.config import PlatformConfig
from gateway.platforms.feishu_adapter import FeishuAdapter


def _adapter() -> FeishuAdapter:
    cfg = PlatformConfig(
        enabled=True,
        extra={"app_id": "cli_test", "app_secret": "secret_test"},
    )
    return FeishuAdapter(cfg)


def test_sync_p2_im_message_dispatch_nonblocking():
    adapter = _adapter()
    loop = asyncio.new_event_loop()
    adapter._main_loop = loop

    started = asyncio.Event()
    release = asyncio.Event()

    async def slow_dispatch(payload: dict) -> None:
        started.set()
        await release.wait()

    mock_lark = MagicMock()
    mock_lark.JSON.marshal.return_value = json.dumps({"event": {}})

    with patch.dict("sys.modules", {"lark_oapi": mock_lark}):
        with patch.object(adapter, "_async_dispatch_p2", side_effect=slow_dispatch):
            with patch("asyncio.run_coroutine_threadsafe", wraps=asyncio.run_coroutine_threadsafe) as rcs:
                t0 = time.monotonic()
                adapter._sync_p2_im_message_receive_v1({"event": {}})
                elapsed = time.monotonic() - t0

    assert elapsed < 0.5, "WS worker thread must return immediately"
    assert rcs.called

    loop.run_until_complete(asyncio.wait_for(started.wait(), timeout=2))
    release.set()
    loop.run_until_complete(asyncio.sleep(0.05))
    loop.close()


def test_sync_p2_logs_dispatch_errors_async():
    adapter = _adapter()
    loop = asyncio.new_event_loop()
    adapter._main_loop = loop

    async def failing_dispatch(payload: dict) -> None:
        raise RuntimeError("dispatch boom")

    mock_lark = MagicMock()
    mock_lark.JSON.marshal.return_value = json.dumps({"event": {}})

    with patch.dict("sys.modules", {"lark_oapi": mock_lark}):
        with patch.object(adapter, "_async_dispatch_p2", side_effect=failing_dispatch):
            adapter._sync_p2_im_message_receive_v1({"event": {}})

    loop.run_until_complete(asyncio.sleep(0.05))
    loop.close()
