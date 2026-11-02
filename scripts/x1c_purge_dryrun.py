#!/usr/bin/env python3
"""x1c_purge_dryrun.py — X1-c「排除规则生效 ⇒ 存量残块自动清」的 **dry-run 读数**工具。

刘哥 2026-10-26 批示：「X1-c 先出 dry-run 0 误伤读数，再谈上线」。
本工具只做两件事，**不删任何生产数据**：
  1) 预测：按生产同一判据（`not exists(join(root,fp)) or excluded_relpath(fp)`）列出
     「下一轮 purge 会删掉的 fp」，逐条标原因（gone / excluded）与风险族（外域绝对路径）。
  2) 自证：在**合成库**上跑生产 `purge_stale()`，断言「预测 == 实删」且外域绝对路径件
     一件不少（负控）；再跑一个变异臂（故意给全 True 谓词）断言检查器**会红**
     —— 两向都过才说明这个 dry-run 有分辨力（单向 = 不及格）。

用法：
    <venv>/python3 ~/.mimiraether/scripts/x1c_purge_dryrun.py --selftest
    <venv>/python3 ~/.mimiraether/scripts/x1c_purge_dryrun.py --db ~/.hermes/wiki_index.db --limit 20
退出码：0 = 0 误伤且自证两向过 / 1 = 有误伤嫌疑或自证失败 / 2 = 环境错
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import tempfile
import time
from pathlib import Path

HOME = Path.home()
HS = HOME / ".hermes/scripts"
sys.path.insert(0, str(HS))

try:
    from exclusion import excluded_relpath  # 口径唯一真源
    from incremental_index import purge_stale, CJK_TABLE  # 生产同一实现
except Exception as exc:  # pragma: no cover
    print("IMPORT_FAIL: %s" % exc)
    sys.exit(2)

SCHEMA = [
    "CREATE TABLE wiki_chunks (id INTEGER PRIMARY KEY, file_path TEXT, content TEXT)",
    "CREATE VIRTUAL TABLE wiki_chunks_fts USING fts5(file_path, content)",
    "CREATE VIRTUAL TABLE wiki_chunks_cjk USING fts5(file_path, bigr)",
    "CREATE TABLE file_hashes (file_path TEXT PRIMARY KEY, content_hash TEXT, updated_at REAL)",
]


def predict(db_path: str, root: str) -> list:
    """只读预测：下一轮 purge_stale 会删掉哪些 fp（生产同一判据，不写库）。"""
    con = sqlite3.connect("file:%s?mode=ro" % db_path, uri=True)
    try:
        # 生产库的 wiki_chunks 是 vec0 虚表 ⇒ 不加载 sqlite_vec 会报 no such module: vec0
        try:
            import sqlite_vec
            con.enable_load_extension(True)
            sqlite_vec.load(con)
            con.enable_load_extension(False)
        except Exception:
            pass
        rows = [r[0] for r in con.execute("SELECT DISTINCT file_path FROM wiki_chunks")]
    finally:
        con.close()
    out = []
    for fp in rows:
        gone = not os.path.exists(os.path.join(root, fp))
        excl = bool(excluded_relpath(fp))
        if gone or excl:
            out.append({
                "fp": fp,
                "reason": "excluded" if (excl and not gone) else "gone",
                "absolute": os.path.isabs(fp),
            })
    return out


def classify(rows: list) -> dict:
    abs_rows = [r for r in rows if r["absolute"]]
    return {
        "would_delete": len(rows),
        "by_reason": {k: sum(1 for r in rows if r["reason"] == k)
                      for k in ("gone", "excluded")},
        "absolute_path_rows": len(abs_rows),      # 外域件被删 = P0 误伤嫌疑
        "abs_sample": [r["fp"] for r in abs_rows[:5]],
    }


def _mkdb(path: str) -> sqlite3.Connection:
    con = sqlite3.connect(path)
    for ddl in SCHEMA:
        con.execute(ddl)
    return con


def _seed(con, rows):
    for fp, exists in rows:
        con.execute("INSERT INTO wiki_chunks(file_path, content) VALUES(?,?)", (fp, "x"))
        con.execute("INSERT INTO wiki_chunks_fts(file_path, content) VALUES(?,?)", (fp, "x"))
        con.execute("INSERT INTO %s(file_path, bigr) VALUES(?,?)" % CJK_TABLE, (fp, "x"))
        con.execute("INSERT INTO file_hashes(file_path, content_hash) VALUES(?,?)", (fp, "h"))


def selftest() -> int:
    """两向自证：①正控（预测==实删 ∧ 外域件保留）②变异臂（坏谓词 ⇒ 必红）。"""
    root = tempfile.mkdtemp(prefix="x1c-dryrun-root-")
    # 造真实存在的文件：一个普通 wiki 件（保留）+ 一个外域件（保留）
    keep_rel = "concepts/keep-me.md"
    os.makedirs(os.path.join(root, "concepts"), exist_ok=True)
    Path(os.path.join(root, keep_rel)).write_text("keep", encoding="utf-8")
    ext_abs = str(HOME / ".hermes/inbox/x1c-ext-keep.md")
    Path(ext_abs).parent.mkdir(parents=True, exist_ok=True)
    Path(ext_abs).write_text("keep", encoding="utf-8")
    # 其余三类：普通件已消失（gone）/ 被排除规则命中（excluded）/ 外域件已消失（gone, 绝对）
    rows = [
        (keep_rel, True),
        (ext_abs, True),
        ("concepts/vanished.md", False),
        ("raw/papers/Memory提纯快照-20261010.md", True),   # 命中 EXCLUDE_FILE_PATTERNS
        (str(HOME / ".hermes/inbox/vanished-ext.md"), False),
    ]
    fails = []
    db_path = os.path.join(root, "_t.db")
    con = _mkdb(db_path)
    _seed(con, rows)
    con.commit()

    pred = predict(db_path, root)
    pred_set = {r["fp"] for r in pred}

    removed = purge_stale(con, root, excluded_relpath)
    con.commit()
    actual_set = {fp for fp, _why in removed}
    left = {r[0] for r in con.execute("SELECT DISTINCT file_path FROM wiki_chunks")}
    con.close()

    if pred_set != actual_set:
        fails.append("预测≠实删: only_pred=%r only_actual=%r"
                     % (sorted(pred_set - actual_set)[:3], sorted(actual_set - pred_set)[:3]))
    must_keep = {keep_rel, ext_abs}
    if not must_keep <= left:
        fails.append("正控件被误删: %r" % sorted(must_keep - left))
    if any(os.path.isabs(fp) for fp in actual_set if fp.endswith("ext-keep.md")):
        fails.append("外域绝对路径件被删（P0 误伤）")

    # ── 变异臂：把谓词换成「恒 True」⇒ 检查器必须报不一致（证明它有分辨力）────
    db2 = os.path.join(root, "_t2.db")
    con2 = _mkdb(db2)
    _seed(con2, rows)
    con2.commit()
    removed_bad = purge_stale(con2, root, lambda _fp: True)
    con2.commit()
    con2.close()
    bad_set = {fp for fp, _why in removed_bad}
    if bad_set == pred_set:
        fails.append("变异臂未触发：坏谓词删的行与预测相同 ⇒ 检查器无分辨力")

    print("[selftest] pred=%d actual=%d 变异臂=%d 正控保留=%d" % (
        len(pred_set), len(actual_set), len(bad_set), len(must_keep & left)))
    print("[selftest] pred_rows=%s" % json.dumps(sorted(pred_set), ensure_ascii=False))
    if fails:
        for f in fails:
            print("[FAIL]", f)
        print("SELFTEST rc=1")
        return 1
    print("SELFTEST rc=0")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--db", default=str(HOME / ".hermes/wiki_index.db"))
    ap.add_argument("--root", default=str(HOME / "wiki"))
    ap.add_argument("--limit", type=int, default=20)
    ap.add_argument("--json-out", default="")
    a = ap.parse_args()

    if a.selftest:
        return selftest()

    t0 = time.time()
    rows = predict(a.db, a.root)
    info = classify(rows)
    info.update({"db": a.db, "root": a.root, "seconds": round(time.time() - t0, 2)})
    print(json.dumps(info, ensure_ascii=False, indent=2))
    for r in rows[:a.limit]:
        print("  %-9s abs=%-5s %s" % (r["reason"], r["absolute"], r["fp"]))
    if a.json_out:
        Path(a.json_out).write_text(json.dumps({"summary": info, "rows": rows},
                                               ensure_ascii=False, indent=2), encoding="utf-8")
        print("[json]", a.json_out)
    # 0 误伤判据：外域绝对路径行数必须为 0（它们绝不该落进删除集）
    return 0 if info["absolute_path_rows"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
