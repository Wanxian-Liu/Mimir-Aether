#!/usr/bin/env python3
"""RS20（四方裁决 §29 Q16 · 2026-09-14）：fts5_search.db 去重。

三件套里的第 ① 件（②=回填幂等改造 `tools/session_search_indexer.py` +
`tools/fts5_search/engine.py`，③=幂等性检查 `scripts/check_fts_idempotency.py`）。

判据（盘上取证，2026-09-14）：
  rows=60,288 · distinct(session_id, content_hash)=54,188 ⇒ 6,100 行同批超额；
  1,771 个重复组的 created_at 跨度**全部 ≤2s** ⇒ 都是同一次回填的重复插入，
  不是"同 session 里真的说了两遍同样的话"。

裁决约束（§29 原文）：
  * 去重前**先备份原库**（152MB 级，快照一份）
  * 保留策略按 **created_at 最新**（同批取任一，因为内容 hash 相同）

保留 = 安全默认：
  * 无 ``--apply`` ⇒ 只打印计划，不写库
  * 任何重复组 created_at 跨度 > ``--max-spread``（默认 60s）⇒ **拒绝执行**
    （那可能是真实重复消息，需人来判，不是脚本能决定的）
  * ``--apply`` 强制先备份（``--no-backup`` 只用于测试库）

用法::

    python3 scripts/dedupe_fts_messages.py                # dry-run，看计划
    python3 scripts/dedupe_fts_messages.py --apply        # 备份 + 去重 + 建唯一索引
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DEFAULT_DB = Path.home() / ".mimiraether" / "data" / "fts5_search.db"
DEFAULT_BACKUP_ROOT = Path.home() / ".mimiraether" / "backups"


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def snapshot_db(src: Path, dest_dir: Path) -> Dict[str, Any]:
    """用 sqlite3 backup API 做**一致快照**（WAL 未落盘的内容也在内）。

    直接文件拷贝会漏掉 ``-wal``；本机当前 WAL 恰好为空，但"恰好"不是机制。
    """
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / src.name
    src_conn = sqlite3.connect(f"file:{src}?mode=ro", uri=True, timeout=30.0)
    dst_conn = sqlite3.connect(str(dest))
    try:
        src_conn.backup(dst_conn)
    finally:
        dst_conn.close()
        src_conn.close()
    digest = _sha256(dest)
    manifest = {
        "source": str(src),
        "snapshot": str(dest),
        "bytes": dest.stat().st_size,
        "sha256": digest,
        "created_by": "scripts/dedupe_fts_messages.py (RS20 §29 Q16)",
    }
    (dest_dir / "MANIFEST.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return manifest


def plan_dedup(conn: sqlite3.Connection) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """算出要删哪些行。返回 (groups, summary)，**不修改**任何东西。

    每个重复组保留 ``created_at`` 最大者（同秒并列取 id 最大）——裁决原文。
    """
    groups: List[Dict[str, Any]] = []
    rows = conn.execute(
        """SELECT session_id, content_hash, COUNT(*) AS n,
                  MIN(created_at) AS mn, MAX(created_at) AS mx
           FROM messages
           GROUP BY session_id, content_hash
           HAVING COUNT(*) > 1
           ORDER BY n DESC"""
    ).fetchall()
    for session_id, content_hash, n, mn, mx in rows:
        keep = conn.execute(
            """SELECT id FROM messages
               WHERE session_id = ? AND content_hash = ?
               ORDER BY created_at DESC, id DESC LIMIT 1""",
            (session_id, content_hash),
        ).fetchone()
        keep_id = int(keep[0]) if keep else None
        victims = [
            int(r[0])
            for r in conn.execute(
                """SELECT id FROM messages
                   WHERE session_id = ? AND content_hash = ? AND id != ?""",
                (session_id, content_hash, keep_id),
            ).fetchall()
        ]
        groups.append(
            {
                "session_id": session_id,
                "content_hash": content_hash,
                "rows": int(n),
                "keep_id": keep_id,
                "victims": victims,
                "spread_s": round(float(mx) - float(mn), 6),
            }
        )
    summary = {
        "dup_groups": len(groups),
        "dup_rows": sum(g["rows"] for g in groups),
        "rows_to_delete": sum(len(g["victims"]) for g in groups),
        "max_spread_s": max((g["spread_s"] for g in groups), default=0.0),
        "groups_spread_gt_60s": sum(1 for g in groups if g["spread_s"] > 60.0),
        "groups_spread_gt_2s": sum(1 for g in groups if g["spread_s"] > 2.0),
    }
    return groups, summary


def apply_dedup(conn: sqlite3.Connection, groups: List[Dict[str, Any]]) -> Dict[str, int]:
    """执行计划：删重复行（含其 FTS 行）+ 重算 sessions.message_count。"""
    victim_ids: List[int] = [vid for g in groups for vid in g["victims"]]
    deleted = 0
    conn.execute("BEGIN IMMEDIATE")
    try:
        for chunk_start in range(0, len(victim_ids), 500):
            chunk = victim_ids[chunk_start : chunk_start + 500]
            marks = ",".join("?" * len(chunk))
            conn.execute(f"DELETE FROM messages_fts WHERE rowid IN ({marks})", chunk)
            cur = conn.execute(f"DELETE FROM messages WHERE id IN ({marks})", chunk)
            deleted += cur.rowcount or 0
        conn.execute(
            """UPDATE sessions SET message_count = COALESCE(
                   (SELECT COUNT(*) FROM messages m WHERE m.session_id = sessions.session_id), 0)"""
        )
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    return {"deleted_rows": deleted, "touched_groups": len(groups)}


def ensure_unique_index(conn: sqlite3.Connection) -> Optional[str]:
    """去重后建立唯一索引（幂等的机制层）。失败返回原因字符串。"""
    from tools.fts5_search.schema import MESSAGES_UNIQUE_INDEX, UNIQUE_INDEX_STATUS_KEY

    try:
        conn.execute(MESSAGES_UNIQUE_INDEX)
    except sqlite3.IntegrityError as exc:
        return f"integrity_error:{exc}"
    conn.execute(
        """INSERT INTO index_status (key, value, updated_at) VALUES (?, 'ok', ?)
           ON CONFLICT(key) DO UPDATE SET value = 'ok', updated_at = excluded.updated_at""",
        (UNIQUE_INDEX_STATUS_KEY, datetime.now().timestamp()),
    )
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--apply", action="store_true", help="真的写库（默认 dry-run）")
    parser.add_argument("--backup-dir", type=Path, default=None)
    parser.add_argument(
        "--no-backup",
        action="store_true",
        help="跳过备份（仅测试库；生产按裁决必须先备份）",
    )
    parser.add_argument("--max-spread", type=float, default=60.0)
    args = parser.parse_args()

    if not args.db.exists():
        print(f"db missing: {args.db}")
        return 2

    conn = sqlite3.connect(str(args.db), timeout=60.0, isolation_level=None)
    conn.execute("PRAGMA busy_timeout=60000")
    try:
        groups, summary = plan_dedup(conn)
        print(f"db={args.db}")
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        if summary["max_spread_s"] > args.max_spread:
            print(
                f"REFUSE: 有重复组 created_at 跨度 {summary['max_spread_s']:.3f}s "
                f"> --max-spread {args.max_spread}s ⇒ 可能是真实重复消息，需人判"
            )
            return 3
        if not groups:
            print("无需去重（0 重复组）")
        elif not args.apply:
            for g in sorted(groups, key=lambda g: -g["rows"])[:5]:
                print(
                    f"  keep id={g['keep_id']} rows={g['rows']} spread={g['spread_s']}s "
                    f"session={g['session_id'][:40]} hash={g['content_hash'][:12]}"
                )
            print("dry-run：加 --apply 执行（会先备份原库）")
            return 0

        if args.apply and groups:
            if not args.no_backup:
                stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
                dest_dir = args.backup_dir or (DEFAULT_BACKUP_ROOT / f"{stamp}-rs20-fts-dedup")
                manifest = snapshot_db(args.db, dest_dir)
                print(f"backup: {manifest['snapshot']} sha256={manifest['sha256'][:16]}...")
            else:
                print("backup: SKIPPED (--no-backup)")
            print(f"dedup: {apply_dedup(conn, groups)}")

        reason = ensure_unique_index(conn)
        print("unique_index:", "created" if reason is None else f"FAILED {reason}")
    finally:
        conn.close()

    # 收尾自检（复用 RS19 待注册的同一检查器）
    from tools.fts5_search.integrity import check_fts_integrity, format_report

    report = check_fts_integrity(args.db)
    print(format_report(report))
    return 0 if report["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
