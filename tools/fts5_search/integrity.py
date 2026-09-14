"""RS20（§29 Q16 · 2026-09-14）：fts5_search.db 的**幂等性自检**。

判决口径（与四方裁决一致："批写入行数 vs distinct hash"）：

| 检查项 | 通过条件 | 为什么 |
|:--|:--|:--|
| `ratio` | `rows / distinct(session_id, content_hash) == 1.0` | 行数多于去重对 = 有重复插入（回填不幂等） |
| `fts_sync` | `COUNT(messages_fts) == COUNT(messages)` | FTS 行与主表 1:1；不等 = 删/插只落一边 |
| `orphan_fts` | `0` | 有 FTS 行拿不到主表 rowid ⇒ 召回里出现"幽灵"内容 |
| `orphan_session` | `0` | messages.session_id 在 sessions 里不存在（FK 未开时的残留） |
| `unique_index` | `index_status` 里 `uniq_messages_session_hash = ok` | 机制层是否真的生效（而不是"代码里写了"） |

**只读**（``mode=ro``）：本模块不得修改被检查的库 —— 检查器自身成为故障源是
RS19 的教训之一。任何一项读不到（表缺失/加锁）都应报 FAIL 而不是 "0"。
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any, Dict, Optional

__all__ = ["check_fts_integrity", "format_report"]

_UNIQUE_KEY = "uniq_messages_session_hash"


def _one(conn: sqlite3.Connection, sql: str, default: Any = None) -> Any:
    row = conn.execute(sql).fetchone()
    if not row:
        return default
    return row[0]


def check_fts_integrity(db_path: Path | str) -> Dict[str, Any]:
    """跑一遍全部判据，返回 (指标 + verdict + failures)。"""
    path = str(db_path)
    report: Dict[str, Any] = {
        "db": path,
        "exists": Path(path).exists(),
        "checks": {},
        "failures": [],
    }
    if not report["exists"]:
        report["failures"].append("db_missing")
        report["verdict"] = "FAIL"
        return report

    uri = f"file:{path}?mode=ro"
    conn = sqlite3.connect(uri, uri=True, timeout=20.0)
    try:
        rows = int(_one(conn, "SELECT COUNT(*) FROM messages", -1))
        fts_rows = int(_one(conn, "SELECT COUNT(*) FROM messages_fts", -1))
        distinct_pairs = int(
            _one(conn, "SELECT COUNT(*) FROM (SELECT DISTINCT session_id, content_hash FROM messages)", -1)
        )
        orphan_fts = int(
            _one(
                conn,
                "SELECT COUNT(*) FROM messages_fts WHERE rowid NOT IN (SELECT id FROM messages)",
                0,
            )
        )
        orphan_session = int(
            _one(
                conn,
                "SELECT COUNT(*) FROM messages m WHERE NOT EXISTS "
                "(SELECT 1 FROM sessions s WHERE s.session_id = m.session_id)",
                0,
            )
        )
        null_hash = int(
            _one(conn, "SELECT COUNT(*) FROM messages WHERE content_hash IS NULL OR content_hash = ''", -1)
        )
        # 唯一索引：以 sqlite_master 为**地面真相**（index_status 是自报，可能过期
        # —— 索引被 DROP 后自报仍写 ok；只信自报 = 又一处"绿着坏"）
        try:
            index_sql = _one(
                conn,
                "SELECT sql FROM sqlite_master WHERE type = 'index' "
                f"AND name = '{_UNIQUE_KEY}'",
                None,
            )
        except sqlite3.Error:
            index_sql = None
        unique_present = bool(index_sql and "UNIQUE" in str(index_sql).upper())
        try:
            unique_status = _one(
                conn, f"SELECT value FROM index_status WHERE key = '{_UNIQUE_KEY}'", None
            )
        except sqlite3.Error:
            unique_status = None

        ratio = (rows / distinct_pairs) if distinct_pairs > 0 else float("inf")
        checks = {
            "rows": rows,
            "fts_rows": fts_rows,
            "distinct_pairs": distinct_pairs,
            "ratio": round(ratio, 6) if ratio != float("inf") else "inf",
            "excess_rows": rows - distinct_pairs,
            "orphan_fts": orphan_fts,
            "orphan_session": orphan_session,
            "null_hash": null_hash,
            "unique_index": "present" if unique_present else "absent",
            "unique_index_status": unique_status,
        }
        report["checks"] = checks

        if rows < 0 or fts_rows < 0 or distinct_pairs < 0 or null_hash < 0:
            report["failures"].append("table_unreadable")
        if ratio != 1.0:
            report["failures"].append(f"dup_rows:excess={checks['excess_rows']}")
        if fts_rows != rows:
            report["failures"].append(f"fts_desync:delta={rows - fts_rows}")
        if orphan_fts:
            report["failures"].append(f"orphan_fts={orphan_fts}")
        if orphan_session:
            report["failures"].append(f"orphan_session={orphan_session}")
        if null_hash:
            report["failures"].append(f"null_hash={null_hash}")
        if not unique_present:
            report["failures"].append(
                f"unique_index=absent(status={unique_status or 'absent'})"
            )
    except sqlite3.Error as exc:
        report["failures"].append(f"sqlite_error:{exc}")
    finally:
        conn.close()

    report["verdict"] = "PASS" if not report["failures"] else "FAIL"
    return report


def format_report(report: Dict[str, Any]) -> str:
    checks = report.get("checks") or {}
    lines = [f"fts5_search.db integrity: {report['db']}"]
    if checks:
        lines.append(
            "  rows={rows} fts_rows={fts_rows} distinct(session,hash)={distinct_pairs} "
            "ratio={ratio} excess={excess_rows}".format(**checks)
        )
        lines.append(
            "  orphan_fts={orphan_fts} orphan_session={orphan_session} "
            "null_hash={null_hash} unique_index={unique_index}".format(**checks)
        )
        lines.append(f"  unique_index_status={checks.get('unique_index_status')}")
    for failure in report.get("failures", []):
        lines.append(f"  FAIL {failure}")
    lines.append(f"VERDICT: {report.get('verdict', 'FAIL')}")
    return "\n".join(lines)
