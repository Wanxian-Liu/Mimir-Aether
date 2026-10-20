"""P0 · 派生搜索索引的写入契约（2026-10-20 根因回归）。

背景（实证 file:line）：
    实测量 sessions_search.db 停写 19h31m，同期 jsonl 正常增长（今日会话
    jsonl=2,361 行 / db=0 行）。根因不是异常被吞（``INDEX-FAIL`` 全仓 0 命中），
    而是**根本没走到调用点**：

        gateway/router/agent_route_mixin.py:921
            agent_persisted = self._session_db is not None
        gateway/router/agent_route_mixin.py:928-930
            append_to_transcript(..., skip_db=agent_persisted)

    而 ``gateway/session.py:1237`` 用**同一个** ``skip_db`` 同时闸住
    「转录库 state.db」与「派生搜索索引 sessions_search.db」：

        if not skip_db:
            self._append_to_sessions_search_index(session_id, message)

    ⇒ 只要 ``_session_db`` 非 None（正常运行态），派生搜索索引就被永久跳过。
    那句注释所依赖的 ``_flush_messages_to_session_db()``
    **在全仓不存在**（grep 仅命中该注释本身），且即便存在也只会写 state.db，
    与 sessions_search.db 是两个不同的库 —— 单边假设，无对侧校验。

两个库、两件事，必须两个开关：
    1. ``skip_db``            → 只管转录库（既有语义，不动）
    2. ``skip_search_index``  → 只管派生搜索索引；默认继承 skip_db，
       以保住 2026-09-12 的「测试载荷不得进生产索引」契约；
       实时路径显式传 False，让真实对话进索引。
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


def _store(tmp_path, db=None):
    from gateway.config import load_gateway_config
    from gateway.session import SessionStore

    return SessionStore(
        tmp_path / "sessions",
        load_gateway_config(),
        transcript_session_db=db if db is not None else MagicMock(),
    )


def test_live_path_skip_db_still_feeds_search_index(tmp_path):
    """实测根因的正面回归：skip_db=True 但 skip_search_index=False ⇒ 索引必须被写。

    这正是实时路径需要的组合：agent 已把消息持久化到转录库，所以跳过转录库写入，
    但**派生索引必须照写**，否则该会话永远搜不到。
    """
    store = _store(tmp_path)
    msg = {"role": "user", "content": "今天说过的话必须能被搜到"}
    with patch.object(store, "_append_to_sessions_search_index") as idx:
        store.append_to_transcript("sid-live", msg, skip_db=True, skip_search_index=False)
    idx.assert_called_once()
    args = idx.call_args[0]
    assert args[0] == "sid-live"
    assert args[1]["content"] == "今天说过的话必须能被搜到"


def test_skip_db_default_still_skips_search_index(tmp_path):
    """负控（契约不回归）：skip_db=True 且未显式覆盖 ⇒ 索引**不得**被写。

    2026-09-12 审计：``skip_db`` 测试载荷曾把 397 行写进生产索引。
    默认值必须保持「一并跳过」，否则该污染会复活。
    """
    store = _store(tmp_path)
    with patch.object(store, "_append_to_sessions_search_index") as idx:
        store.append_to_transcript("sid-test", {"role": "user", "content": "x"}, skip_db=True)
    idx.assert_not_called()


def test_normal_append_feeds_search_index(tmp_path):
    """正控：默认参数（实时常态的另一半）也必须写索引。"""
    store = _store(tmp_path)
    with patch.object(store, "_append_to_sessions_search_index") as idx:
        store.append_to_transcript("sid-normal", {"role": "user", "content": "y"})
    idx.assert_called_once()


def test_rewrite_live_path_skip_db_still_feeds_search_index(tmp_path):
    """rewrite 路径同病同治（/retry /undo /compress 走这里）。"""
    store = _store(tmp_path)
    msgs = [{"role": "user", "content": "a"}]
    with patch.object(store, "_rewrite_sessions_search_index") as idx:
        store.rewrite_transcript("sid-rw", msgs, skip_db=True, skip_search_index=False)
    idx.assert_called_once()
