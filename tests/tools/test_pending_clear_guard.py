"""F7(2026-10-19): pending 清空必须「有校验」，禁无条件 clear。

事故（2026-10-19 03:10:04 实证）：startup_resume 把 `index_pending.json` 从
`{"20261019_022057_9dc448fa": {"total": 1952}}` 直接清成 `{}`，而该会话在 chroma
里只有 249 条、源库 475 行 —— 补进多少完全没被读回校验，于是「清空」被当成
「补完」。这是第三处「失败即静默」。

修法（本文件即其判据）：
- 纯函数 `_pending_clear_decision(wanted, chroma_docs)` 决定能不能清；
- resume 路径用**读回**（chroma 实有 doc 数）当判据，不用自报进度；
- 重写路径用**写者自报**（本路径每条 message 的 upsert 返回值）——它手里有
  权威读数；但不足额同样不许清。
"""
from __future__ import annotations

import json

import pytest

from tools import chroma_session_indexer as csi
from tools import session_search_indexer as ssi
from tools.session_search_tool import SessionSearchDB

SID = "sess-guard"


@pytest.fixture()
def state_paths(tmp_path, monkeypatch):
    wm = tmp_path / "index_watermark.json"
    pd = tmp_path / "index_pending.json"
    monkeypatch.setenv("MIMIR_INDEX_WATERMARK_PATH", str(wm))
    monkeypatch.setenv("MIMIR_INDEX_PENDING_PATH", str(pd))
    monkeypatch.setenv("MIMIR_CHROMA_DIR", str(tmp_path / "chroma"))
    monkeypatch.setattr(csi, "sync_message_to_chroma", lambda *a, **k: True)
    monkeypatch.setattr(csi, "sync_session_chroma_from_db", lambda *a, **k: 0)
    return wm, pd


def _db(tmp_path):
    return SessionSearchDB(str(tmp_path / "search.db"))


# ── 纯函数：四臂（两向）────────────────────────────────────────────────

def test_decision_incomplete_keeps_pending():
    """缺额 ⇒ 不许清（负控：这是事故当天的形态 3/10）。"""
    ok, reason = ssi._pending_clear_decision(wanted=10, chroma_docs=3)
    assert ok is False
    assert reason == "incomplete"


def test_decision_complete_clears():
    """足额 ⇒ 清（正控）。"""
    ok, reason = ssi._pending_clear_decision(wanted=10, chroma_docs=10)
    assert ok is True
    assert reason == "complete"


def test_decision_over_count_clears():
    ok, reason = ssi._pending_clear_decision(wanted=10, chroma_docs=12)
    assert ok is True


def test_decision_empty_session_clears():
    """源库该会话已无行（压缩删掉）⇒ 无事可补，允许清。"""
    ok, reason = ssi._pending_clear_decision(wanted=0, chroma_docs=0)
    assert ok is True
    assert reason == "empty_session"


# ── resume 路径：读回校验 ─────────────────────────────────────────────

def test_resume_incomplete_does_not_clear(tmp_path, state_paths, monkeypatch):
    """事故复现：resume 自称跑过，但 chroma 实际只到 3/10 ⇒ pending 必须留着。"""
    wm, pd = state_paths
    db = _db(tmp_path)
    ssi.record_pending(SID, 10, source="t", title="T")
    monkeypatch.setattr(
        ssi, "resume_session_index",
        lambda sid, **kw: {"session_id": sid, "indexed_rows": 10, "chroma_docs": 0, "filled": 0},
    )
    monkeypatch.setattr(ssi, "_count_session_docs", lambda sid, **kw: 3)

    out = ssi.resume_pending_indexes(like_db=db)

    rec = json.loads(pd.read_text())
    assert SID in rec, "缺额却清空了 pending = 事故复现"
    assert rec[SID]["actual"] == 10
    assert rec[SID]["chroma_docs"] == 3
    assert rec[SID]["reason"] == "incomplete"
    assert out["resumed"][SID]["pending_cleared"] is False


def test_resume_complete_clears(tmp_path, state_paths, monkeypatch):
    """正控：读回足额 ⇒ 清，且回报 pending_cleared=True。"""
    wm, pd = state_paths
    db = _db(tmp_path)
    ssi.record_pending(SID, 10, source="t", title="T")
    monkeypatch.setattr(
        ssi, "resume_session_index",
        lambda sid, **kw: {"session_id": sid, "indexed_rows": 10, "filled": 10},
    )
    monkeypatch.setattr(ssi, "_count_session_docs", lambda sid, **kw: 10)

    out = ssi.resume_pending_indexes(like_db=db)

    assert json.loads(pd.read_text()) == {}
    assert out["resumed"][SID]["pending_cleared"] is True


def test_resume_error_does_not_clear(tmp_path, state_paths, monkeypatch):
    """报错 ⇒ 不清（即使 chroma 数字看着够，也不拿假读数放行）。"""
    wm, pd = state_paths
    db = _db(tmp_path)
    ssi.record_pending(SID, 10, source="t", title="T")
    monkeypatch.setattr(
        ssi, "resume_session_index",
        lambda sid, **kw: {"session_id": sid, "error": "Boom: x", "indexed_rows": 10},
    )
    monkeypatch.setattr(ssi, "_count_session_docs", lambda sid, **kw: 99)

    out = ssi.resume_pending_indexes(like_db=db)

    assert SID in json.loads(pd.read_text())
    assert out["resumed"][SID]["pending_cleared"] is False


def test_resume_unverifiable_does_not_clear(tmp_path, state_paths, monkeypatch):
    """读回失败（返回 None）⇒ 不清：无读数不许当「补完了」。"""
    wm, pd = state_paths
    db = _db(tmp_path)
    ssi.record_pending(SID, 10, source="t", title="T")
    monkeypatch.setattr(
        ssi, "resume_session_index",
        lambda sid, **kw: {"session_id": sid, "indexed_rows": 10, "filled": 10},
    )
    monkeypatch.setattr(ssi, "_count_session_docs", lambda sid, **kw: None)

    out = ssi.resume_pending_indexes(like_db=db)

    assert SID in json.loads(pd.read_text())
    assert out["resumed"][SID]["pending_reason"] == "unverified"


# ── 重写路径：写者自报不足额同样不许清 ────────────────────────────────

def test_rewrite_partial_index_does_not_clear(tmp_path, state_paths, monkeypatch):
    """有 message upsert 失败（count < 应有）⇒ pending 留着，别把半成品当完成。"""
    wm, pd = state_paths
    db = _db(tmp_path)
    monkeypatch.setattr(ssi, "index_transcript_message", lambda *a, **k: False)

    n = ssi.reindex_session_transcript(
        SID, [{"role": "user", "content": f"m{i}"} for i in range(5)], like_db=db, source="t"
    )

    assert n == 0
    rec = json.loads(pd.read_text())
    assert SID in rec
    assert rec[SID]["actual"] == 5
    assert rec[SID]["reason"] == "incomplete"


def test_rewrite_full_index_clears(tmp_path, state_paths):
    """正控：全部写成功 ⇒ pending 清空（既有行为不得回归）。"""
    wm, pd = state_paths
    db = _db(tmp_path)

    n = ssi.reindex_session_transcript(
        SID, [{"role": "user", "content": f"m{i}"} for i in range(5)], like_db=db, source="t"
    )

    assert n == 5
    assert json.loads(pd.read_text()) == {}
