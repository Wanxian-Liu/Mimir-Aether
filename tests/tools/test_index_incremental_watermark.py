"""① 增量水位 / ② 断点续传 回归（P0 诊断 2026-10-05 S8）。"""
from __future__ import annotations

import json
import sqlite3

import pytest

from tools import chroma_session_indexer as csi
from tools import session_search_indexer as ssi
from tools.session_search_tool import SessionSearchDB


@pytest.fixture()
def state_paths(tmp_path, monkeypatch):
    """沙箱：状态文件 + chroma 写入出口都指到 tmp（不碰生产索引）。"""
    wm = tmp_path / "index_watermark.json"
    pd = tmp_path / "index_pending.json"
    monkeypatch.setenv("MIMIR_INDEX_WATERMARK_PATH", str(wm))
    monkeypatch.setenv("MIMIR_INDEX_PENDING_PATH", str(pd))
    monkeypatch.setenv("MIMIR_CHROMA_DIR", str(tmp_path / "chroma"))
    monkeypatch.setattr(csi, "sync_message_to_chroma", lambda *a, **k: True)
    monkeypatch.setattr(csi, "sync_session_chroma_from_db", lambda *a, **k: 0)
    return wm, pd


def _row_ids(db_path, sid="s1"):
    con = sqlite3.connect(str(db_path))
    try:
        return [r[0] for r in con.execute(
            "SELECT id FROM messages WHERE session_id = ? ORDER BY id", (sid,))]
    finally:
        con.close()


def _msgs(n, prefix="m"):
    return [{"role": "user", "content": f"{prefix}{i}"} for i in range(n)]


def _db(tmp_path):
    return SessionSearchDB(str(tmp_path / "search.db"))


def test_first_pass_indexes_everything_and_records_watermark(tmp_path, state_paths):
    wm, pd = state_paths
    db = _db(tmp_path)
    n = ssi.reindex_session_transcript("s1", _msgs(5), like_db=db, source="t")
    assert n == 5
    rec = json.loads(wm.read_text())["s1"]
    assert rec["n"] == 5
    assert json.loads(pd.read_text()) == {}


def test_unchanged_prefix_is_not_reindexed(tmp_path, state_paths):
    wm, pd = state_paths
    db = _db(tmp_path)
    msgs = _msgs(5)
    ssi.reindex_session_transcript("s1", msgs, like_db=db, source="t")
    ids_before = _row_ids(db.db_path)
    # 第二次：前缀完全未变 ⇒ keep_first=5 ⇒ 只补尾部
    n2 = ssi.reindex_session_transcript("s1", msgs + _msgs(2, "tail"), like_db=db, source="t")
    assert n2 == 2
    ids_after = _row_ids(db.db_path)
    assert ids_after[:5] == ids_before, "前缀行被重建（水位失效）"
    assert len(ids_after) == 7


def test_changed_prefix_falls_back_to_full_rebuild(tmp_path, state_paths):
    db = _db(tmp_path)
    ssi.reindex_session_transcript("s1", _msgs(5), like_db=db, source="t")
    changed = [{"role": "user", "content": "rewritten"}] + _msgs(4, "x")
    ids_before = _row_ids(db.db_path)
    n = ssi.reindex_session_transcript("s1", changed, like_db=db, source="t")
    assert n == 5
    assert ssi.watermark_prefix_len("s1", changed) == 5
    assert _row_ids(db.db_path) != ids_before, "前缀变了却仍然续用旧行（水位判据失效）"


def test_watermark_ignores_longer_messages(tmp_path, state_paths):
    db = _db(tmp_path)
    ssi.reindex_session_transcript("s1", _msgs(3), like_db=db, source="t")
    assert ssi.watermark_prefix_len("s1", _msgs(2)) == 0


def test_pending_marker_written_before_indexing(tmp_path, state_paths, monkeypatch):
    wm, pd = state_paths
    db = _db(tmp_path)

    def _boom(*_a, **_k):
        raise RuntimeError("killed mid-way")

    monkeypatch.setattr(ssi, "index_transcript_message", _boom)
    with pytest.raises(RuntimeError):
        ssi.reindex_session_transcript("s9", _msgs(4), like_db=db, source="t")
    assert "s9" in json.loads(pd.read_text())
    assert ssi.pending_index_report()


def test_resume_fills_only_missing_chroma_docs(tmp_path, state_paths, monkeypatch):
    wm, pd = state_paths
    db = _db(tmp_path)
    db.add_session("s1", source="t")
    for i in range(3):
        db.add_message("s1", "user", f"c{i}")
    calls = {}

    class _Col:
        def get(self, where=None, include=None, limit=None, offset=0):
            return {"ids": ["s1:1"]} if offset == 0 else {"ids": []}

    def _upsert(batch, collection=None):
        calls["batch"] = [m.message_id for m in batch]
        return len(batch)

    monkeypatch.setattr("tools.chroma_session_indexer.get_chroma_collection", lambda *a, **k: _Col())
    monkeypatch.setattr("tools.chroma_session_indexer.upsert_indexed_messages", _upsert)
    out = ssi.resume_session_index("s1", like_db=db)
    assert out["indexed_rows"] == 3
    assert out["chroma_docs"] == 1
    assert out["filled"] == 2
    assert calls["batch"] == [2, 3]


def test_resume_pending_clears_marker(tmp_path, state_paths, monkeypatch):
    wm, pd = state_paths
    db = _db(tmp_path)
    pd.write_text(json.dumps({"s1": {"total": 1}}))
    monkeypatch.setattr(
        ssi, "resume_session_index",
        lambda sid, like_db=None, **k: {"session_id": sid, "filled": 0},
    )
    out = ssi.resume_pending_indexes(like_db=db)
    assert out["pending_seen"] == 1
    assert json.loads(pd.read_text()) == {}
