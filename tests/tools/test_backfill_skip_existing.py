"""补缺口语义：默认跳过已存在 doc，全量必须显式 skip_existing=False。

2026-10-20 事故回归：`backfill_chroma_sessions()` 原先对每一条都重算嵌入
（86,081 条 ≈33 小时），而缺口只有 2,399 条；运维手册又指向该入口，
于是「补缺口」变成「全量重嵌」。
"""

from __future__ import annotations

from tools.chroma_session_indexer import backfill_chroma_sessions
from tools.session_search_tool import SessionSearchDB


class FakeCollection:
    """最小集合替身：只实现 backfill 用到的 get/upsert。"""

    def __init__(self, ids=None):
        self.ids = set(ids or [])
        self.upsert_calls = []

    def get(self, include=None):
        return {"ids": sorted(self.ids)}

    def upsert(self, ids=None, documents=None, metadatas=None):
        self.upsert_calls.append(list(ids or []))
        self.ids |= set(ids or [])


def _seed(db_path, n=3):
    db = SessionSearchDB(str(db_path))
    db.add_session("s1", source="cli", title="t")
    for i in range(n):
        db.add_message("s1", "user", f"消息 {i}")
    return db


def test_skip_existing_indexes_nothing_when_all_present(tmp_path):
    """正控：满库跑一次 ⇒ 嵌入 0 条。"""
    db_path = tmp_path / "sessions_search.db"
    _seed(db_path)
    # 第一次全量补齐
    col = FakeCollection()
    first = backfill_chroma_sessions(db_path, collection=col)
    assert first.messages_indexed == 3
    # 第二次：全部已存在 ⇒ 一条都不嵌
    col.upsert_calls.clear()
    second = backfill_chroma_sessions(db_path, collection=col)
    assert second.messages_indexed == 0
    assert second.messages_skipped == 3
    assert col.upsert_calls == []


def test_skip_existing_only_fills_gap(tmp_path):
    """缺口场景：已有 1 条 ⇒ 只嵌剩下 2 条。"""
    db_path = tmp_path / "sessions_search.db"
    _seed(db_path)
    col = FakeCollection(ids=["s1:1"])
    stats = backfill_chroma_sessions(db_path, collection=col)
    assert stats.messages_indexed == 2
    assert stats.messages_skipped == 1
    assert col.upsert_calls == [["s1:2", "s1:3"]]


def test_full_rebuild_reembeds_everything(tmp_path):
    """负控：显式 skip_existing=False ⇒ 仍全量重嵌，跳过逻辑不能吞掉这个能力。"""
    db_path = tmp_path / "sessions_search.db"
    _seed(db_path)
    col = FakeCollection(ids=["s1:1", "s1:2", "s1:3"])
    stats = backfill_chroma_sessions(db_path, collection=col, skip_existing=False)
    assert stats.messages_indexed == 3
    assert stats.messages_skipped == 0
