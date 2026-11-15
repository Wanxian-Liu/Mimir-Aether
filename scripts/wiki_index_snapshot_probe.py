"""索引快照对读探针 —— 活体 vs 重切前备份的 wiki_chunks 块数。

判据用途：证明「同一索引存在两个块数」是**快照时点差**，不是口径差。
用法: ~/src/MimirAether/.venv/bin/python3 scripts/wiki_index_snapshot_probe.py
退出码: 0 = 两库均可读；1 = 有库缺失或不可读
"""
import sqlite3
import sys
from pathlib import Path

HOME = Path.home()
sys.path.insert(0, str(HOME / "src/MimirAether"))

try:
    import sqlite_vec
except ImportError:
    sqlite_vec = None

DBS = {
    "LIVE  ~/.hermes/wiki_index.db": HOME / ".hermes/wiki_index.db",
    "PRE   wiki_index.pre-rechunk-20261115.db": HOME / ".hermes/data/wiki_index.pre-rechunk-20261115.db",
}

rc = 0
for label, db in DBS.items():
    print("=" * 70)
    print(label, "->", db)
    if not db.exists():
        print("  MISSING")
        rc = 1
        continue
    con = sqlite3.connect("file:%s?mode=ro" % db, uri=True)
    if sqlite_vec:
        con.enable_load_extension(True)
        sqlite_vec.load(con)
    cur = con.cursor()
    try:
        total = cur.execute("SELECT COUNT(*) FROM wiki_chunks").fetchone()[0]
    except Exception as e:
        print("  ERR", e)
        rc = 1
        con.close()
        continue
    print("  wiki_chunks rows:", total)
    cols = [r[1] for r in cur.execute("PRAGMA table_info(wiki_chunks)").fetchall()]
    for col in ("layer", "collection"):
        if col in cols:
            print("  --- %s ---" % col)
            for row in cur.execute("SELECT %s, COUNT(*) FROM wiki_chunks GROUP BY %s ORDER BY 2 DESC LIMIT 8" % (col, col)):
                print("     ", row)
    con.close()

sys.exit(rc)
