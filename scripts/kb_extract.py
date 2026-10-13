#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
kb_extract.py — 知识库「抽取管线」（L5-S4′ 产物 ② · 幂等）

定位（对齐会议卡 L5 / S4′）：挂在**既有** 6h 增量索引 cron **之后**（不新建 cron）。
索引（`~/.hermes/wiki_index.db`）是**块级**存储；本件把它抽成**文件级知识单元清单**
（每文件：块数 / 内容哈希 / 索引时间 / 代表块首行），供「知识库统一」层消费。
**只读**索引库，不写回。

设计（角色卡 L63「Design your metadata schema before your index schema」）：
  * **schema 先解析**：先读 `wiki_chunks` 的 DDL 判形态——
      ① vec0 虚表 ⇒ 列序反推后映射 shadow 表 `wiki_chunks_metadatatextNN`（不硬编码列名）；
      ② 普通表   ⇒ 直接按列名读（也让 `--selftest` 无需扩展即可跑）。
    换列序/换形态时会**报错或走对分支**，而不是静默错抽。
  * **不依赖 sqlite-vec 扩展**：只读 shadow 普通表（vec0 虚表要扩展才能 SELECT，
    索引器 venv 有、别的解释器未必有 ⇒ 依赖它 = 判据换解释器就 rc=2）。
  * **幂等**：产物**不含时间戳**；记录按 path 排序 + JSON `sort_keys=True`
    ⇒ 同输入（DB 内容不变）重跑 ⇒ **字节相同**（`--check` 判据）。
  * **原子写**：tmp + `os.replace`。

用法：
  ~/src/MimirAether/.venv/bin/python3 scripts/kb_extract.py --dry-run
  ~/src/MimirAether/.venv/bin/python3 scripts/kb_extract.py
  ~/src/MimirAether/.venv/bin/python3 scripts/kb_extract.py --check
  ~/src/MimirAether/.venv/bin/python3 scripts/kb_extract.py --selftest

退出码：0=ok/一致 · 1=不一致 · 2=源缺失/结构不可解析
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sqlite3
import sys
import tempfile

DEFAULT_DB = os.path.expanduser("~/.hermes/wiki_index.db")
DEFAULT_OUT = os.path.expanduser("~/.mimiraether/data/kb/wiki_extract.jsonl")
VTABLE = "wiki_chunks"
BODY_NAMES = ("chunk_type", "content", "text", "chunk", "body")
HEAD_CHARS = 80


def _ddl(con, name):
    row = con.execute(
        "SELECT sql FROM sqlite_master WHERE name=? AND type='table'", (name,)
    ).fetchone()
    return row[0] if row and row[0] else None


def parse_meta_columns(con):
    """vec0 形态：从 DDL 反推 [(meta 列名, shadow 文本表)]。"""
    ddl = _ddl(con, VTABLE)
    if not ddl:
        raise ValueError("源库无 %s 表" % VTABLE)
    m = re.search(r"USING\s+vec0\s*\((.*)\)\s*$", ddl, re.S | re.I)
    if not m:
        return None                                        # 普通表 ⇒ 直读模式
    shadows, k = [], 0
    for raw in m.group(1).split(","):
        raw = raw.strip()
        if not raw:
            continue
        name = raw.split()[0].strip('"').strip("`")
        rest = raw[len(name):].strip()
        if re.search(r"float\s*\[|int8\s*\[|bit\s*\[", rest, re.I):
            continue                                       # 向量列不入 shadow 映射
        shadows.append((name, "wiki_chunks_metadatatext%02d" % k))
        k += 1
    if not shadows:
        raise ValueError("%s 无可抽取的 metadata 文本列" % VTABLE)
    return shadows


def _table_exists(con, name):
    return bool(
        con.execute("SELECT COUNT(*) FROM sqlite_master WHERE name=?", (name,)).fetchone()[0]
    )


def _cols(con, table):
    return [r[1] for r in con.execute("PRAGMA table_info(%s)" % table)]


def extract(db_path):
    """返回 (records, stats)。records 按 path 排序；纯函数式（无写盘）。"""
    con = sqlite3.connect("file:%s?mode=ro" % db_path, uri=True)
    try:
        shadows = parse_meta_columns(con)
        per_file, last_map, head_map = {}, {}, {}
        if shadows:                                        # ① vec0 shadow 模式
            missing = [t for _, t in shadows if not _table_exists(con, t)]
            if missing:
                raise ValueError("shadow 表缺失: %s" % ",".join(missing))
            path_col = shadows[0][1]
            for rid, p in con.execute(
                "SELECT rowid, data FROM %s WHERE data IS NOT NULL ORDER BY rowid" % path_col
            ):
                per_file.setdefault(p, []).append(rid)
            last_col = shadows[-1][1] if len(shadows) > 1 else None
            if last_col and last_col != path_col:
                last_map = {r: v for r, v in con.execute("SELECT rowid, data FROM %s" % last_col)}
            body_col = None
            for name, tbl in shadows[1:-1]:
                if name.lower() in BODY_NAMES:
                    body_col = tbl
                    break
            if body_col is None and len(shadows) > 2:
                body_col = shadows[2][1]
            if body_col:
                head_map = {
                    r: v for r, v in con.execute(
                        "SELECT rowid, data FROM %s WHERE data IS NOT NULL" % body_col
                    )
                }
        else:                                              # ② 普通表直读模式
            cols = _cols(con, VTABLE)
            if "file_path" not in cols:
                raise ValueError("%s 无 file_path 列（schema 不可解析）" % VTABLE)
            last_name = "last_indexed_at" if "last_indexed_at" in cols else None
            body_name = next((c for c in BODY_NAMES if c in cols), None)
            sel = ["rowid", "file_path"] + ([last_name] if last_name else []) + \
                  ([body_name] if body_name else [])
            for row in con.execute("SELECT %s FROM %s" % (",".join(sel), VTABLE)):
                rid, p = row[0], row[1]
                per_file.setdefault(p, []).append(rid)
                i = 2
                if last_name:
                    last_map[rid] = row[i]
                    i += 1
                if body_name:
                    head_map[rid] = row[i]
        hashes = {}
        if _table_exists(con, "file_hashes"):
            hashes = {
                p: (h, u) for p, h, u in con.execute(
                    "SELECT file_path, content_hash, updated_at FROM file_hashes"
                )
            }
    finally:
        con.close()

    records = []
    for p in sorted(per_file):
        rids = per_file[p]
        h, u = hashes.get(p, (None, None))
        head = None
        for rid in rids:
            v = head_map.get(rid)
            if v:
                head = str(v).strip().replace("\n", " ")[:HEAD_CHARS]
                break
        records.append({
            "path": p,
            "chunks": len(rids),
            "content_hash": h,
            "hash_updated_at": u,
            "last_indexed_at": last_map.get(rids[0]),
            "first_chunk_head": head,
        })
    stats = {
        "files_with_chunks": len(per_file),
        "chunks_total": sum(len(v) for v in per_file.values()),
        "file_hashes_total": len(hashes),
        "orphan_hash_only": len(set(hashes) - set(per_file)),
        "orphan_chunk_only": len(set(per_file) - set(hashes)),
    }
    return records, stats


def render(records):
    lines = [
        json.dumps(r, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        for r in records
    ]
    return ("\n".join(lines) + ("\n" if lines else "")).encode("utf-8")


def _atomic_write(path, data):
    d = os.path.dirname(path) or "."
    os.makedirs(d, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=d, prefix=".kb_extract-", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def run(db_path, out_path, dry_run=False, check=False):
    if not os.path.exists(db_path):
        print("KB_EXTRACT: UNKNOWN  源缺失: %s" % db_path)
        print("  => rc=2")
        return 2
    try:
        records, stats = extract(db_path)
    except (ValueError, sqlite3.DatabaseError) as exc:
        print("KB_EXTRACT: UNKNOWN  抽取失败: %s" % exc)
        print("  => rc=2")
        return 2
    data = render(records)
    print("KB_EXTRACT: files=%d chunks=%d hashes=%d orphan_hash_only=%d orphan_chunk_only=%d"
          % (stats["files_with_chunks"], stats["chunks_total"], stats["file_hashes_total"],
             stats["orphan_hash_only"], stats["orphan_chunk_only"]))
    print("  digest=%s bytes=%d" % (hashlib.sha256(data).hexdigest(), len(data)))
    print("  产物位=%s" % out_path)
    if dry_run:
        print("  持久化：否（dry-run）")
        print("  => rc=0")
        return 0
    if check:
        if not os.path.exists(out_path):
            print("  产物不存在 => rc=1")
            return 1
        old = open(out_path, "rb").read()
        same = old == data
        print("  IDEMPOTENT: %s  on_disk_bytes=%d new_bytes=%d" % (same, len(old), len(data)))
        if not same:
            o = set(old.decode("utf-8", "replace").splitlines())
            n = set(data.decode("utf-8").splitlines())
            print("  diff_lines=%d" % (len(n - o) + len(o - n)))
        print("  => rc=%d" % (0 if same else 1))
        return 0 if same else 1
    _atomic_write(out_path, data)
    print("  wrote ok")
    print("  => rc=0")
    return 0


def _mkfixture(path, rows):
    con = sqlite3.connect(path)
    con.execute("CREATE TABLE wiki_chunks (rowid INTEGER PRIMARY KEY, file_path TEXT,"
                " frontmatter TEXT, chunk_type TEXT, last_indexed_at TEXT)")
    con.execute("CREATE TABLE file_hashes (file_path TEXT PRIMARY KEY, content_hash TEXT,"
                " updated_at REAL)")
    con.executemany("INSERT INTO wiki_chunks VALUES (?,?,?,?,?)", rows)
    con.executemany("INSERT INTO file_hashes VALUES (?,?,?)",
                    [("a.md", "h1", 1.0), ("b.md", "h2", 2.0), ("c.md", "h3", 3.0)])
    con.commit()
    con.close()


def selftest():
    """档位④ 两向：正控（幂等链 rc=0）· 负控（改字节 ⇒ rc=1；源缺失/无虚表 ⇒ rc=2）。"""
    tmp = tempfile.mkdtemp(prefix="kb-extract-selftest-")
    db, out = os.path.join(tmp, "idx.db"), os.path.join(tmp, "out.jsonl")
    _mkfixture(db, [(1, "a.md", "{}", "H:alpha", "2026-10-13 08:00"),
                    (2, "a.md", "{}", "H:beta", "2026-10-13 08:00"),
                    (3, "b.md", "{}", "H:gamma", "2026-10-13 08:00")])
    cases = [
        ("正控①dry-run rc0", run(db, out, dry_run=True), 0),
        ("正控②首写 rc0", run(db, out), 0),
        ("正控③重跑（幂等）rc0", run(db, out), 0),
        ("正控④--check 一致 rc0", run(db, out, check=True), 0),
    ]
    with open(out, "ab") as fh:                            # 负控①：产物被改一字节
        fh.write(b'{"path":"zzz.md"}\n')
    cases.append(("负控①产物被改 --check rc1", run(db, out, check=True), 1))
    run(db, out)                                           # 复原
    cases.append(("负控②源缺失 rc2", run(os.path.join(tmp, "nope.db"), out), 2))
    empty = os.path.join(tmp, "empty.db")                  # 负控③：无 wiki_chunks 表
    con = sqlite3.connect(empty)
    con.execute("CREATE TABLE t (a) ")
    con.commit()
    con.close()
    cases.append(("负控③无虚表 rc2", run(empty, out), 2))
    bad = 0
    for name, got, want in cases:
        ok = got == want
        bad += 0 if ok else 1
        print("  [%s] %s got=%d want=%d" % ("OK" if ok else "MISMATCH", name, got, want))
    print("KB_EXTRACT SELFTEST %s (%d/%d)" % ("PASS" if bad == 0 else "FAIL",
                                              len(cases) - bad, len(cases)))
    return 0 if bad == 0 else 1


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=DEFAULT_DB)
    ap.add_argument("--out", default=DEFAULT_OUT)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    if a.dry_run and a.check:
        print("--dry-run 与 --check 互斥")
        return 2
    return run(a.db, a.out, dry_run=a.dry_run, check=a.check)


if __name__ == "__main__":
    sys.exit(main())
