"""P0-b · 重放必须真幂等（治「UNIQUE(session_id, seq) 挡不住重复」）。

实证（2026-10-20）：
    ``add_message`` 用 ``next_seq = MAX(seq)+1`` 生成 seq，**永远不撞 UNIQUE**。
    实测同一会话重放两次：``delta=30`` 而非 0 —— 「UNIQUE 防重复回填」是假保护。
    这同时解释了 10-20 01:09 那次 sessions_search.db +49,469 行膨胀：
    继承副本会话被整段重放，每行都拿到新的 MAX+1。

修法：seq 允许由调用方显式给出（= 会话内可搜索消息的 1-based 序号）。
     重放同一转录 ⇒ 产出同一批 seq ⇒ 撞 UNIQUE ⇒ 返回 0（已索引，不重复插入）。
     实时路径不传 seq，仍走 MAX+1（行为不变）。
"""
from __future__ import annotations

import sqlite3


def _db(tmp_path):
    from tools.session_search_tool import SessionSearchDB

    return SessionSearchDB(str(tmp_path / "ss.db")), tmp_path / "ss.db"


def _count(db_path, sid):
    con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        return con.execute(
            "SELECT COUNT(*) FROM messages WHERE session_id=?", (sid,)
        ).fetchone()[0]
    finally:
        con.close()


def test_explicit_seq_replay_is_idempotent(tmp_path):
    """正控：同一批显式 seq 重放两次 ⇒ 行数不变、第二次返回 0。"""
    db, path = _db(tmp_path)
    db.add_session("s1", source="t", title="t")

    ids1 = [db.add_message("s1", "user", f"m{i}", seq=i) for i in (1, 2, 3)]
    n1 = _count(path, "s1")
    assert n1 == 3
    assert all(i > 0 for i in ids1), f"首轮应全部插入成功: {ids1}"

    ids2 = [db.add_message("s1", "user", f"m{i}", seq=i) for i in (1, 2, 3)]
    n2 = _count(path, "s1")
    assert n2 == 3, f"重放不得增行：{n1} -> {n2}"
    assert ids2 == [0, 0, 0], f"撞 UNIQUE 应返回 0（已索引），实得 {ids2}"


def test_explicit_seq_extends_beyond_existing(tmp_path):
    """正控：重放可在已有前缀之后继续追加（1,2 已存在 ⇒ 只插 3）。"""
    db, path = _db(tmp_path)
    db.add_session("s2", source="t", title="t")
    db.add_message("s2", "user", "a", seq=1)
    db.add_message("s2", "user", "b", seq=2)
    assert _count(path, "s2") == 2

    ids = [db.add_message("s2", "user", c, seq=i) for i, c in ((1, "a"), (2, "b"), (3, "c"))]
    assert _count(path, "s2") == 3
    assert ids[0] == 0 and ids[1] == 0 and ids[2] > 0, f"应为 0,0,>0 实得 {ids}"


def test_auto_seq_still_works_for_live_path(tmp_path):
    """负控（行为不变）：不传 seq ⇒ 仍按 MAX+1 追加，三条都在。"""
    db, path = _db(tmp_path)
    db.add_session("s3", source="t", title="t")
    for i in range(3):
        db.add_message("s3", "user", f"live{i}")
    assert _count(path, "s3") == 3

    con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        seqs = [r[0] for r in con.execute(
            "SELECT seq FROM messages WHERE session_id='s3' ORDER BY seq")]
    finally:
        con.close()
    assert seqs == [1, 2, 3], f"实时路径应得到连续 seq，实得 {seqs}"
