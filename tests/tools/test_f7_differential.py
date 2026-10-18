"""F7 受控差分（不依赖任何新符号 ⇒ 旧版也能跑，红/绿才是行为差而非 API 差）。

唯一变量 = 是否打了 F7 补丁。
预期：旧版 ⇒ pending 被无条件清空 ⇒ 本用例 **FAIL**；新版 ⇒ 保留 ⇒ PASS。
"""
from __future__ import annotations

import json

import pytest

from tools import chroma_session_indexer as csi
from tools import session_search_indexer as ssi
from tools.session_search_tool import SessionSearchDB


class _FakeCol:
    """零模型加载的假集合：resume 读回时报告「本会话 0 条」。"""

    def get(self, **kw):
        return {"ids": []}

    def delete(self, **kw):
        return None


def test_differential_unfilled_pending_must_survive(tmp_path, monkeypatch):
    pd = tmp_path / "index_pending.json"
    monkeypatch.setenv("MIMIR_INDEX_WATERMARK_PATH", str(tmp_path / "index_watermark.json"))
    monkeypatch.setenv("MIMIR_INDEX_PENDING_PATH", str(pd))
    monkeypatch.setenv("MIMIR_CHROMA_DIR", str(tmp_path / "chroma"))
    monkeypatch.setattr(csi, "sync_message_to_chroma", lambda *a, **k: True)
    monkeypatch.setattr(csi, "sync_session_chroma_from_db", lambda *a, **k: 0)
    monkeypatch.setattr(csi, "_get_incremental_collection", lambda *a, **k: _FakeCol())

    sid = "probe-sess"
    ssi.record_pending(sid, 10, source="probe", title="T")
    monkeypatch.setattr(
        ssi, "resume_session_index",
        lambda s, **kw: {"session_id": s, "indexed_rows": 10, "filled": 0, "chroma_docs": 0},
    )
    db = SessionSearchDB(str(tmp_path / "search.db"))

    ssi.resume_pending_indexes(like_db=db)

    rec = json.loads(pd.read_text())
    assert sid in rec, "缺口未填却清空 pending（F7 事故形态）"
