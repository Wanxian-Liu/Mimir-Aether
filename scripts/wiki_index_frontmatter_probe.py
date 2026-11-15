"""frontmatter 键分布探针 —— 证明索引内 schema 分裂（4 键块 + 8 键块并存）。

判据用途：推翻「relations/derived_from 均不入索引」；同时证明「按键统计」的指标会随重切漂移。
用法: ~/src/MimirAether/.venv/bin/python3 scripts/wiki_index_frontmatter_probe.py
退出码: 0 = 可读且完成统计；1 = 库缺失/不可读
"""
import json
import sqlite3
import sys
from collections import Counter
from pathlib import Path

HOME = Path.home()
sys.path.insert(0, str(HOME / "src/MimirAether"))

try:
    import sqlite_vec
except ImportError:
    sqlite_vec = None

db = HOME / ".hermes/wiki_index.db"
if not db.exists():
    print("MISSING", db)
    sys.exit(1)

con = sqlite3.connect("file:%s?mode=ro" % db, uri=True)
if sqlite_vec:
    con.enable_load_extension(True)
    sqlite_vec.load(con)
cur = con.cursor()

total = cur.execute("SELECT COUNT(*) FROM wiki_chunks").fetchone()[0]
print("total chunks:", total)

rows = cur.execute("SELECT frontmatter FROM wiki_chunks LIMIT 3000").fetchall()
keycnt, bad = Counter(), 0
for (fm,) in rows:
    try:
        d = json.loads(fm) if fm else {}
    except Exception:
        bad += 1
        continue
    for k in d:
        keycnt[k] += 1
print("parse failures in 3000:", bad)
print("top keys (of 3000):")
for k, v in keycnt.most_common(15):
    print("   %s: %s" % (k, v))

print("\n=== 8 键非空 chunk 数（full scan）===")
KEYS = ["status", "tags", "confidence", "based_on", "type", "date", "relations", "derived_from"]
for k in KEYS:
    q = ("SELECT COUNT(*) FROM wiki_chunks "
         "WHERE json_extract(frontmatter, '$.%s') IS NOT NULL "
         "  AND json_extract(frontmatter, '$.%s') != '[]' "
         "  AND json_extract(frontmatter, '$.%s') != '' " % (k, k, k))
    try:
        print("   %s: %s" % (k, cur.execute(q).fetchone()[0]))
    except Exception as e:
        print("   %s: ERR %s" % (k, e))

con.close()
sys.exit(0)
