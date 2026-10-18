"""增量重写后的 chroma 孤儿清理（2026-10-12 · 1454 孤儿事故回归）。

病灶（实测坐实，session `20261012_092909_2b38e89f`）：
    `reindex_session_transcript`（`/compress` 调用）里
      keep = watermark_prefix_len(...) = 1195（前缀未变）
      clear_session_messages(sid, keep_first=1195)     # 保留最老 1195 行
        => 删 id 48451..49871（**1421 行**）
      重插 compressed[1195:] = 123 条 => AUTOINCREMENT 续号 49872..49994
      if keep == 0:   <- **假** => chroma 全量重同步被跳过
    => 被删 1421 行的 `{sid}:{id}` doc 永久滞留 = 1421 孤儿。

修法：`keep > 0` 分支改走 `prune_session_chroma_orphans`（只删过期 id，**不重嵌**）。
不能简单拆掉 `keep == 0` 守卫 —— 那会全量重嵌，正是 2026-10-05 P0 被 30s 预算截断的那件事。

反证保留：**追加**（前缀未变且无行被删）不产孤儿 => prune 在该场景必须是 no-op。
"""
from __future__ import annotations

import sqlite3

import pytest

from tools import chroma_session_indexer as csi
from tools import session_search_indexer as ssi
from tools.session_search_tool import SessionSearchDB


class _FakeCollection:
    """最小 chroma 替身：只实现 prune 用到的 get / delete。"""

    def __init__(self, ids=None):
        self.ids = set(ids or [])
        self.deleted: list = []

    def get(self, where=None, include=None, limit=None, offset=0):
        sid = (where or {}).get("session_id")
        rows = sorted(i for i in self.ids if sid is None or i.startswith(f"{sid}:"))
        return {"ids": rows[offset:offset + (limit or 1000)]}

    def delete(self, ids=None, where=None):
        self.deleted.extend(ids or [])
        for i in ids or []:
            self.ids.discard(i)


@pytest.fixture()
def env(tmp_path, monkeypatch):
    wm = tmp_path / "index_watermark.json"
    pd = tmp_path / "index_pending.json"
    monkeypatch.setenv("MIMIR_INDEX_WATERMARK_PATH", str(wm))
    monkeypatch.setenv("MIMIR_INDEX_PENDING_PATH", str(pd))
    monkeypatch.setattr(csi, "chroma_incremental_enabled", lambda: True)
    return wm, pd


def _msgs(n, prefix="m"):
    return [{"role": "user", "content": f"{prefix}{i}"} for i in range(n)]


def _row_ids(db_path, sid="s1"):
    con = sqlite3.connect(str(db_path))
    try:
        return [r[0] for r in con.execute(
            "SELECT id FROM messages WHERE session_id = ? ORDER BY id", (sid,))]
    finally:
        con.close()


# ---------------------------------------------------------------- 单元（prune 本体）

def test_prune_removes_only_stale_ids(tmp_path, env):
    """正控：源已无的 doc 被删；源仍在的 doc 一条不动。"""
    db = SessionSearchDB(str(tmp_path / "search.db"))
    db.add_session("s1", source="t")
    ids = [db.add_message("s1", "user", f"c{i}") for i in range(3)]
    col = _FakeCollection([f"s1:{i}" for i in ids] + ["s1:999", "s1:1000"])
    out = csi.prune_session_chroma_orphans("s1", db.db_path, collection=col)
    assert out["chroma_docs"] == 5
    assert out["wanted"] == 3
    assert out["orphans"] == 2
    assert out["deleted"] == 2
    assert sorted(col.deleted) == ["s1:1000", "s1:999"]
    assert all(f"s1:{i}" in col.ids for i in ids), "源仍在的 doc 被误删"


def test_prune_is_noop_on_clean_session(tmp_path, env):
    """负控：干净 session => 0 孤儿、0 删除（不得空删）。"""
    db = SessionSearchDB(str(tmp_path / "search.db"))
    db.add_session("s1", source="t")
    ids = [db.add_message("s1", "user", f"c{i}") for i in range(2)]
    col = _FakeCollection([f"s1:{i}" for i in ids])
    out = csi.prune_session_chroma_orphans("s1", db.db_path, collection=col)
    assert out["orphans"] == 0 and out["deleted"] == 0
    assert col.deleted == []
    assert len(col.ids) == 2


def test_prune_does_not_touch_other_sessions(tmp_path, env):
    """负控：跨 session 隔离 —— 邻居 session 的 doc 不得被删。"""
    db = SessionSearchDB(str(tmp_path / "search.db"))
    db.add_session("s1", source="t")
    db.add_session("s2", source="t")
    i1 = db.add_message("s1", "user", "a")
    i2 = db.add_message("s2", "user", "b")
    col = _FakeCollection([f"s1:{i1}", "s1:888", f"s2:{i2}", "s2:777"])
    out = csi.prune_session_chroma_orphans("s1", db.db_path, collection=col)
    assert out["deleted"] == 1
    assert col.deleted == ["s1:888"]
    assert f"s2:{i2}" in col.ids and "s2:777" in col.ids, "邻居 session 被误删"


def test_prune_dry_run_deletes_nothing(tmp_path, env):
    """读数与动作分离：dry_run 只报数不删。"""
    db = SessionSearchDB(str(tmp_path / "search.db"))
    db.add_session("s1", source="t")
    db.add_message("s1", "user", "a")
    col = _FakeCollection(["s1:999"])
    out = csi.prune_session_chroma_orphans("s1", db.db_path, collection=col, dry_run=True)
    assert out["orphans"] == 1 and out["deleted"] == 0
    assert col.deleted == [] and "s1:999" in col.ids


def test_prune_skipped_when_incremental_writer_off(tmp_path, env, monkeypatch):
    """配对不变量：增量写者关闭时不清理（否则把「陈旧」换成「缺失」）。"""
    monkeypatch.setattr(csi, "chroma_incremental_enabled", lambda: False)
    db = SessionSearchDB(str(tmp_path / "search.db"))
    db.add_session("s1", source="t")
    db.add_message("s1", "user", "a")
    col = _FakeCollection(["s1:999"])
    out = csi.prune_session_chroma_orphans("s1", db.db_path, collection=col)
    assert out["deleted"] == 0 and col.deleted == []


# ------------------------------------------------- 活体路径（走 reindex 的真分支）

def _wire(monkeypatch, col):
    monkeypatch.setattr(
        csi, "sync_message_to_chroma",
        lambda msg: col.ids.add(csi.message_doc_id(msg.session_id, msg.message_id)) or True,
    )
    monkeypatch.setattr(csi, "_get_incremental_collection", lambda *a, **k: col)


def test_compress_shaped_rewrite_prunes_orphans(tmp_path, env, monkeypatch):
    """活体路径 · 复刻真事故形状：水位命中(keep>0) + 尾部行被删 => 孤儿必须被清。

    这是 1454 孤儿那次的真实形状（保留头 + 重插尾，删中间/尾部），
    不是单纯的追加（见下一个用例：追加不产孤儿）。
    """
    db = SessionSearchDB(str(tmp_path / "search.db"))
    col = _FakeCollection()
    _wire(monkeypatch, col)

    msgs = _msgs(4)
    ssi.reindex_session_transcript("s1", msgs, like_db=db, source="t")   # 首过 => 水位 n=4
    for i in range(8):                                                    # 会话继续：追 8 条
        ssi.index_transcript_message(
            "s1", {"role": "user", "content": f"appended{i}"},
            like_db=db, source="t", ensure_session=False,
        )
    before = _row_ids(db.db_path)
    assert len(before) == 12
    assert col.ids == {f"s1:{i}" for i in before}

    # /compress：前 4 条未变（水位命中 => keep=4）+ 新增 2 条
    ssi.reindex_session_transcript("s1", msgs + _msgs(2, "tail"), like_db=db, source="t")

    after = _row_ids(db.db_path)
    deleted = set(before) - set(after)
    assert deleted, "前置条件不成立：本轮无行被删 => 复现不了孤儿（用例失去意义）"
    wanted = {f"s1:{i}" for i in after}
    assert col.ids == wanted, f"孤儿残留: {sorted(col.ids - wanted)}"


def test_append_only_rewrite_creates_no_orphans(tmp_path, env, monkeypatch):
    """反证（保留第一版测试的发现）：纯追加 => 无行被删 => 无孤儿、prune 是 no-op。"""
    db = SessionSearchDB(str(tmp_path / "search.db"))
    col = _FakeCollection()
    _wire(monkeypatch, col)

    msgs = _msgs(3)
    ssi.reindex_session_transcript("s1", msgs, like_db=db, source="t")
    before = _row_ids(db.db_path)
    ssi.reindex_session_transcript("s1", msgs + _msgs(2, "tail"), like_db=db, source="t")
    after = _row_ids(db.db_path)

    assert set(before) <= set(after), "追加不该删行"
    assert col.ids == {f"s1:{i}" for i in after}


def test_without_prune_hook_orphans_would_persist(tmp_path, env, monkeypatch):
    """负控（= 修前行为）：把**清理钩子**打成 no-op => 孤儿必须残留。

    2026-10-18 解耦后清理不再走 `csi.prune_session_chroma_orphans`（全库扫描旧路径），
    改锚 `ssi._delete_stale_session_docs`——负控锚点必须跟着实现走，否则锚在
    被解耦掉的那条路上，绿得没有鉴别力。

    证明 test_compress_shaped_rewrite_prunes_orphans 真有鉴别力 ——
    否则「绿」可能只是因为那条路径本来就不产生孤儿。两向缺一即不及格。
    """
    db = SessionSearchDB(str(tmp_path / "search.db"))
    col = _FakeCollection()
    _wire(monkeypatch, col)
    monkeypatch.setattr(
        ssi, "_delete_stale_session_docs",
        lambda *a, **k: {"seeded": 0, "present": 0, "deleted": 0},
    )

    msgs = _msgs(4)
    ssi.reindex_session_transcript("s1", msgs, like_db=db, source="t")
    for i in range(8):
        ssi.index_transcript_message(
            "s1", {"role": "user", "content": f"appended{i}"},
            like_db=db, source="t", ensure_session=False,
        )
    ssi.reindex_session_transcript("s1", msgs + _msgs(2, "tail"), like_db=db, source="t")

    after = _row_ids(db.db_path)
    wanted = {f"s1:{i}" for i in after}
    leftover = col.ids - wanted
    assert leftover, "打掉 prune 后仍无孤儿 => 本用例无鉴别力（绿是假的）"
