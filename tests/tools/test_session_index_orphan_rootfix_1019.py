"""F1/F4 根治用例（2026-10-19 · DBRE）：

F1 —— keep=0 时点名清理：旧形态 `_stale_docs_before_clear(keep<=0)` 返回 `([],0)`，
      caller 走全量 resync（删除被 except 吞掉）⇒ 旧 doc 与新 doc 并存 = 孤儿。
F4 —— 水位阶梯：`watermark_prefix_len` 遇 `n > len(messages)`（压缩后消息变短）直接
      返回 0 ⇒ 该会话**永远** keep=0。改为在阶梯上回退到仍匹配的最大前缀。

两向判据：正向该删的删 / 该进 incremental 的进；负向头部变了必须回 0（不许假匹配）。
"""
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import tools.session_search_indexer as ssi


def _mk_db(tmp_path, rows):
    """rows = [(id, session_id, content)] -> 最小 messages 表。"""
    db = tmp_path / "sessions_search.db"
    con = sqlite3.connect(str(db))
    con.execute(
        "CREATE TABLE messages (id INTEGER PRIMARY KEY, session_id TEXT, role TEXT,"
        " content TEXT, timestamp REAL, tool_name TEXT)"
    )
    for mid, sid, content in rows:
        con.execute(
            "INSERT INTO messages (id, session_id, role, content, timestamp)"
            " VALUES (?,?,?,?,?)",
            (mid, sid, "user", content, 0.0),
        )
    con.commit()
    con.close()
    return db


# ── F1：keep<=0 必须点名「clear 会删掉的全部行」 ──────────────────────────
def test_f1_keep_zero_names_all_rows(tmp_path):
    sid = "s_keep0"
    db = _mk_db(tmp_path, [(1, sid, "a"), (2, sid, "b"), (3, sid, "c")])
    docs, ceiling = ssi._stale_docs_before_clear(sid, db, 0)
    assert len(docs) == 3, "keep=0 => clear 删全部行 => 必须点名 3 个 doc（旧行为 0）"
    assert ceiling == 3
    assert all(d.startswith(sid + ":") for d in docs)


def test_f1_keep_zero_negative_other_sessions_untouched(tmp_path):
    """负控：别的会话的行不许进名单（白名单作用域）。"""
    db = _mk_db(
        tmp_path,
        [(1, "s_a", "a"), (2, "s_other", "x"), (3, "s_other", "y")],
    )
    docs, _ = ssi._stale_docs_before_clear("s_a", db, 0)
    assert docs == ["s_a:1"], docs


def test_f1_keep_positive_unchanged(tmp_path):
    """回归：keep>0 语义不变（只点名 keep 之后的尾部）。"""
    sid = "s_keep2"
    db = _mk_db(tmp_path, [(1, sid, "a"), (2, sid, "b"), (3, sid, "c")])
    docs, ceiling = ssi._stale_docs_before_clear(sid, db, 2)
    assert docs == [f"{sid}:3"], docs
    assert ceiling == 3


# ── F4：压缩后消息变短，水位必须阶梯回退而不是归零 ───────────────────────
def _msgs(n, prefix="m"):
    return [{"role": "user", "content": f"{prefix}{i}"} for i in range(n)]


def test_f4_watermark_ladder_survives_shrink(tmp_path, monkeypatch):
    monkeypatch.setattr(ssi, "_watermark_path", lambda: tmp_path / "wm.json")
    sid = "s_shrink"
    full = _msgs(100)
    ssi.record_watermark(sid, full)
    shrunk = full[:40]
    assert ssi.watermark_prefix_len(sid, shrunk) > 0, (
        "压缩后 n>len 就归零 = 该会话永远 keep=0（旧行为）"
    )


def test_f4_watermark_ladder_negative_head_changed(tmp_path, monkeypatch):
    """负控：头部内容变了 ⇒ 必须回 0，不许假匹配。"""
    monkeypatch.setattr(ssi, "_watermark_path", lambda: tmp_path / "wm.json")
    sid = "s_changed"
    ssi.record_watermark(sid, _msgs(100))
    changed = [{"role": "user", "content": "DIFFERENT"} for _ in range(40)]
    assert ssi.watermark_prefix_len(sid, changed) == 0


def test_f4_watermark_exact_prefix_still_exact(tmp_path, monkeypatch):
    """回归：长度没缩时保持精确值。"""
    monkeypatch.setattr(ssi, "_watermark_path", lambda: tmp_path / "wm.json")
    sid = "s_exact"
    m = _msgs(64)
    ssi.record_watermark(sid, m)
    assert ssi.watermark_prefix_len(sid, m) == 64


# ── F1 配套：大批量删除必须分批（blast radius） ───────────────────────────
class _FakeCollection:
    def __init__(self, have):
        self.have = set(have)
        self.calls = []

    def get(self, where=None, include=None, limit=1000, offset=0):
        ids = sorted(self.have)[offset:offset + limit]
        return {"ids": ids}

    def delete(self, ids=None):
        self.calls.append(list(ids))
        for i in ids:
            self.have.discard(i)


def test_f1_delete_batches_large_lists(monkeypatch):
    sid = "s_big"
    docs = [f"{sid}:{i}" for i in range(2500)]
    fake = _FakeCollection(docs)
    import tools.chroma_session_indexer as csi
    monkeypatch.setattr(csi, "_get_incremental_collection", lambda: fake, raising=False)
    monkeypatch.setattr(csi, "chroma_incremental_enabled", lambda: True, raising=False)
    out = ssi._delete_stale_session_docs(sid, docs)
    assert out["deleted"] == 2500, out
    assert len(fake.calls) >= 2, "2500 条须分批删除，不许单次巨型 delete"
    assert fake.have == set()
