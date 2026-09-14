"""RS20（四方裁决 §29 Q16 · 2026-09-14）：fts5_search 去重 + 回填幂等 + 幂等性检查。

三层各测各的：
  ① 去重（`scripts/dedupe_fts_messages.py`）：保留 created_at 最新，删重复行 + 其 FTS 行
  ② 回填幂等（`tools/session_search_indexer.py` + `tools/fts5_search/engine.py`）：
     重跑同一 transcript 不得新增行（机制 = `uniq_messages_session_hash` 唯一约束）
  ③ 幂等性检查（`tools/fts5_search/integrity.py`）：重复存在时 FAIL，去重后 PASS
"""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.dedupe_fts_messages import apply_dedup, ensure_unique_index, plan_dedup  # noqa: E402
from tools.fts5_search.engine import FTS5SearchEngine  # noqa: E402
from tools.fts5_search.integrity import check_fts_integrity  # noqa: E402
from tools.session_search_indexer import backfill_sessions  # noqa: E402

TS1 = "2026-09-11T16:08:10"
TS2 = "2026-09-11T16:09:10"
TS1_EPOCH = 1789114090.0  # 2026-09-11 16:08:10 UTC+8（与取证同一时刻）


def _write_transcript(sessions_dir: Path, session_id: str = "sess-a") -> None:
    sessions_dir.mkdir(parents=True, exist_ok=True)
    rows = [
        {"role": "session_meta", "platform": "feishu"},
        {"role": "user", "content": "alpha bravo", "timestamp": TS1},
        {"role": "assistant", "content": "charlie delta", "timestamp": TS2},
    ]
    with (sessions_dir / f"{session_id}.jsonl").open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    (sessions_dir / "sessions.json").write_text(
        json.dumps({session_id: {"session_id": session_id, "platform": "feishu", "title": "t"}}),
        encoding="utf-8",
    )


def _counts(db_path: Path):
    conn = sqlite3.connect(str(db_path))
    try:
        rows = conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
        fts = conn.execute("SELECT COUNT(*) FROM messages_fts").fetchone()[0]
        return rows, fts
    finally:
        conn.close()


# ── ② 回填幂等 ──────────────────────────────────────────────────────────────


def test_index_message_dedupes_same_session_content(tmp_path):
    engine = FTS5SearchEngine(str(tmp_path / "e.db"))
    try:
        first = engine.index_message("s1", "user", "same text")
        second = engine.index_message("s1", "user", "same text")
        assert first > 0
        assert second == 0, "重复插入必须被唯一约束挡下并返回 0（= 跳过）"
        assert _counts(tmp_path / "e.db") == (1, 1), "主表与 FTS 表都必须只有 1 行"
    finally:
        engine.close()


def test_index_message_allows_same_text_in_other_session(tmp_path):
    engine = FTS5SearchEngine(str(tmp_path / "e2.db"))
    try:
        assert engine.index_message("s1", "user", "same text") > 0
        assert engine.index_message("s2", "user", "same text") > 0
        assert _counts(tmp_path / "e2.db") == (2, 2)
    finally:
        engine.close()


def test_index_batch_dedupes_and_counts_only_inserted(tmp_path):
    engine = FTS5SearchEngine(str(tmp_path / "e3.db"))
    try:
        indexed = engine.index_batch(
            [
                {"session_id": "s1", "role": "user", "content": "dup"},
                {"session_id": "s1", "role": "user", "content": "dup"},
                {"session_id": "s1", "role": "user", "content": "unique"},
            ]
        )
        assert indexed == 2
        assert _counts(tmp_path / "e3.db") == (2, 2)
        count = engine._conn.execute(
            "SELECT message_count FROM sessions WHERE session_id = 's1'"
        ).fetchone()[0]
        assert count == 2, "message_count 只应统计真正插入的行"
    finally:
        engine.close()


def test_backfill_rerun_is_idempotent(tmp_path):
    sessions_dir = tmp_path / "sessions"
    fts_db = tmp_path / "fts.db"
    _write_transcript(sessions_dir)

    first = backfill_sessions(sessions_dir, like_db_path=None, fts_db_path=fts_db)
    assert first.fts_messages == 2
    assert first.fts_duplicates_skipped == 0
    assert (first.fts_rows, first.fts_distinct_pairs, first.fts_ratio) == (2, 2, 1.0)

    second = backfill_sessions(sessions_dir, like_db_path=None, fts_db_path=fts_db)
    assert second.fts_messages == 0, "第二次回填不得新增任何行"
    assert second.fts_duplicates_skipped == 2
    assert _counts(fts_db) == (2, 2)
    assert check_fts_integrity(fts_db)["verdict"] == "PASS"


def test_backfill_persists_transcript_timestamp(tmp_path):
    sessions_dir = tmp_path / "sessions2"
    fts_db = tmp_path / "fts2.db"
    _write_transcript(sessions_dir)
    backfill_sessions(sessions_dir, like_db_path=None, fts_db_path=fts_db)
    conn = sqlite3.connect(str(fts_db))
    try:
        values = sorted(r[0] for r in conn.execute("SELECT created_at FROM messages").fetchall())
    finally:
        conn.close()
    # 不再是 now()：两条消息的 created_at 差 = transcript 里两条的间隔（60s）
    assert values[1] - values[0] == 60.0


# ── ① 去重（保留 created_at 最新） ─────────────────────────────────────────


def _db_with_duplicates(path: Path, *, spread_s: float = 0.0) -> None:
    """建一个**含重复**的库：先建 schema，再拆唯一索引，再手工灌重复行。"""
    engine = FTS5SearchEngine(str(path))
    engine.close()
    conn = sqlite3.connect(str(path))
    conn.execute("DROP INDEX IF EXISTS uniq_messages_session_hash")
    conn.execute(
        "INSERT OR IGNORE INTO sessions (session_id, source, title, created_at, updated_at) "
        "VALUES ('s1', 'test', 't', ?, ?)",
        (TS1_EPOCH, TS1_EPOCH),
    )
    base = TS1_EPOCH
    for idx, ts in enumerate([base, base + spread_s, base + spread_s]):
        cur = conn.execute(
            "INSERT INTO messages (session_id, role, content, content_hash, created_at) "
            "VALUES ('s1', 'user', 'dup content', 'hash-dup', ?)",
            (ts,),
        )
        conn.execute("INSERT INTO messages_fts (rowid, content) VALUES (?, 'dup content')", (cur.lastrowid,))
    conn.commit()
    conn.close()


def test_plan_and_apply_keeps_latest_created_at(tmp_path):
    db_path = tmp_path / "dups.db"
    _db_with_duplicates(db_path)
    conn = sqlite3.connect(str(db_path))
    try:
        groups, summary = plan_dedup(conn)
        assert summary["dup_groups"] == 1
        assert summary["rows_to_delete"] == 2
        assert len(groups[0]["victims"]) == 2
        keep_ts = conn.execute(
            "SELECT created_at FROM messages WHERE id = ?", (groups[0]["keep_id"],)
        ).fetchone()[0]
        assert keep_ts == TS1_EPOCH, "保留的必须是 created_at 最新那一行"
        assert apply_dedup(conn, groups)["deleted_rows"] == 2
        assert ensure_unique_index(conn) is None
    finally:
        conn.close()
    assert _counts(db_path) == (1, 1), "重复行及其 FTS 行都要删掉"


def test_spread_is_reported_for_refusal(tmp_path):
    db_path = tmp_path / "spread.db"
    _db_with_duplicates(db_path, spread_s=3600.0)
    conn = sqlite3.connect(str(db_path))
    try:
        _groups, summary = plan_dedup(conn)
        assert summary["max_spread_s"] == 3600.0
        assert summary["groups_spread_gt_60s"] == 1, "跨度 >60s 的组必须被标出来（主流程据此拒绝）"
    finally:
        conn.close()


# ── ③ 幂等性检查 ───────────────────────────────────────────────────────────


def test_integrity_check_fails_on_duplicates_then_passes(tmp_path):
    db_path = tmp_path / "chk.db"
    _db_with_duplicates(db_path)
    report = check_fts_integrity(db_path)
    assert report["verdict"] == "FAIL"
    assert any(f.startswith("dup_rows") for f in report["failures"])
    assert any(f.startswith("unique_index=absent") for f in report["failures"])

    conn = sqlite3.connect(str(db_path))
    try:
        groups, _ = plan_dedup(conn)
        apply_dedup(conn, groups)
        ensure_unique_index(conn)
    finally:
        conn.close()

    fixed = check_fts_integrity(db_path)
    assert fixed["verdict"] == "PASS", fixed["failures"]
    assert fixed["checks"]["ratio"] == 1.0
    assert fixed["checks"]["unique_index"] == "present"
    assert fixed["checks"]["unique_index_status"] == "ok"


def test_integrity_check_ignores_same_hash_across_sessions(tmp_path):
    """同一句话在不同会话里是**正常数据**，不得判为重复（RS20 口径纠偏）。"""
    engine = FTS5SearchEngine(str(tmp_path / "cross.db"))
    try:
        engine.index_message("s1", "user", "shared phrase")
        engine.index_message("s2", "user", "shared phrase")
    finally:
        engine.close()
    report = check_fts_integrity(tmp_path / "cross.db")
    assert report["verdict"] == "PASS", report["failures"]
    assert report["checks"]["ratio"] == 1.0


def test_integrity_check_missing_db(tmp_path):
    report = check_fts_integrity(tmp_path / "nope.db")
    assert report["verdict"] == "FAIL"
    assert "db_missing" in report["failures"]
