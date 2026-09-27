"""2026-09-27: 旧文本已读回执（「刘哥读了你的消息」）默认关闭。

GLANCE 表情已在同一时刻提供 read 反馈（机器可读、不刷屏）。本用例钉住三件事：
1. 默认关（不发文本）；2. 开关打开后恢复发送（=> 闸有鉴别力，不是恒不发）；
3. 收据追踪 _read_receipts 在两种情况下都必须保留（那是有价值的半边）。
受控差分：同一输入、仅 READ_TEXT_FEEDBACK 不同 => 结果必须相反。
"""

from __future__ import annotations

import asyncio
import json
import os
from unittest.mock import MagicMock, patch

from gateway.config import PlatformConfig
from gateway.platforms.feishu_adapter import FeishuAdapter

_SRC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                  "gateway", "platforms", "feishu_adapter.py")
_ENV_KEY = "MIMIR_FEISHU_READ_TEXT_FEEDBACK"


def _adapter():
    cfg = PlatformConfig(enabled=True, extra={"app_id": "cli_test", "app_secret": "secret_test"})
    a = FeishuAdapter(cfg)
    for attr in ("_read_receipts", "_sent_msg_chat", "_last_read_feedback_at"):
        if not hasattr(a, attr):
            setattr(a, attr, {})
    a._main_loop = asyncio.new_event_loop()
    return a


def _payload(mid):
    return {"event": {"reader": {"reader_id": "ou_reader", "reader_type": "user"},
                      "message_id_list": [mid]}}


def _fire(adapter, mid="om_test_1", register_chat=True):
    if register_chat:
        adapter._sent_msg_chat[mid] = "oc_test_chat"
    payload = _payload(mid)
    mock_lark = MagicMock()
    mock_lark.JSON.marshal.return_value = json.dumps(payload)
    with patch.dict("sys.modules", {"lark_oapi": mock_lark}):
        adapter._lark_noop_message_read_v1(payload)
    return mid


def test_default_off_does_not_send_text_but_tracks_receipt():
    a = _adapter()
    with patch("asyncio.run_coroutine_threadsafe") as rcs:
        mid = _fire(a)
    assert not rcs.called, "默认关时不得发送文本回执"
    assert mid in a._read_receipts, "收据追踪必须保留（有价值的半边）"


def test_enabled_restores_send():
    """受控差分的另一半：同输入、仅开关不同 => 必须相反。"""
    a = _adapter()
    a.READ_TEXT_FEEDBACK = True
    with patch("asyncio.run_coroutine_threadsafe") as rcs:
        mid = _fire(a)
    assert rcs.called, "开关打开后必须恢复发送，否则闸恒关（无鉴别力）"
    assert mid in a._read_receipts


def test_throttle_marks_chat_when_enabled():
    a = _adapter()
    a.READ_TEXT_FEEDBACK = True
    with patch("asyncio.run_coroutine_threadsafe"):
        _fire(a)
    assert a._last_read_feedback_at.get("oc_test_chat", 0.0) > 0.0


def test_empty_message_id_list_is_noop():
    a = _adapter()
    payload = {"event": {"message_id_list": []}}
    mock_lark = MagicMock()
    mock_lark.JSON.marshal.return_value = json.dumps(payload)
    with patch.dict("sys.modules", {"lark_oapi": mock_lark}):
        with patch("asyncio.run_coroutine_threadsafe") as rcs:
            a._lark_noop_message_read_v1(payload)
    assert not rcs.called


def test_enabled_without_loop_does_not_raise():
    a = _adapter()
    a.READ_TEXT_FEEDBACK = True
    a._main_loop = None
    with patch("asyncio.run_coroutine_threadsafe") as rcs:
        _fire(a)
    assert not rcs.called


def test_unknown_chat_mapping_does_not_send():
    a = _adapter()
    a.READ_TEXT_FEEDBACK = True
    with patch("asyncio.run_coroutine_threadsafe") as rcs:
        _fire(a, mid="om_never_sent", register_chat=False)
    assert not rcs.called


def test_structure_default_is_off_and_gate_present():
    src = open(_SRC, encoding="utf-8").read()
    assert 'os.getenv("' + _ENV_KEY + '") or "0"' in src, "默认值必须是 0（关）"
    assert "if not self.READ_TEXT_FEEDBACK:" in src, "闸必须存在"
    assert src.count(_ENV_KEY) >= 3

