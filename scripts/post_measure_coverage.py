"""H2 覆盖度报告：`applied` 里有多少真的拿到了 post 实计（结算率）。

背景（2026-09-17）：`applied 78 / post_measure 1` ⇒ 结算率 **1.3%** —— 真因是
`gateway/platforms/api_server.py:1538` 在 `_run_agent()` 体内建 agent，每 run 一个
新 compressor ⇒ 挂账是**实例字段** ⇒ 跨 run 结算结构上不可能。H2 加了跨 run
持久化 ⇒ **本脚本是它的效果度量**（没有度量就不许说「修好了」）。

口径（写进输出，防下次误读）：
  · `applied`  = 真正落地的压缩（`outcome == "applied"` 且非 `kind=post_measure` 行）
  · `settled`  = 拿到 post 实计的（`settle_reason == "settled"`）
  · 覆盖率     = settled / applied
  · `settle_source`：`same_run` / `cross_run` / `pre_h2`（字段缺失 = H2 之前的历史行）

用法：`.venv/bin/python3 scripts/post_measure_coverage.py [--min-coverage 0.5] [--json]`
退出码：0 = 达标；1 = 未达标；2 = **目标文件不存在**（显式失败，不静默返 0）。
"""
import argparse
import json
import sys
from collections import Counter
from pathlib import Path

# 与 scripts/ 下同族脚本一致：本文件直接跑时 sys.path[0] 是 scripts/，
# 不注入 repo 根就 import 不到 mimir_constants（**首版就栽在这**：import 失败被
# `except` 吞掉 ⇒ 悄悄退回相对路径 ⇒ 报「file not found」而真因是 import 错）。
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mimir_constants import get_mimir_home  # noqa: E402

PRE_H2 = "pre_h2"


def load_rows(path):
    rows, bad = [], 0
    with open(path, encoding="utf-8") as f:
        for ln, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except Exception:
                bad += 1
    return rows, bad


def analyze(rows):
    applied = 0
    post = []
    for r in rows:
        if r.get("kind") == "post_measure":
            post.append(r)
        elif r.get("outcome") == "applied":
            applied += 1
    reasons = Counter(str(r.get("settle_reason")) for r in post)
    sources = Counter(str(r.get("settle_source") or PRE_H2) for r in post)
    settled = reasons.get("settled", 0)
    coverage = (settled / applied) if applied else None
    return {
        "applied": applied,
        "post_rows": len(post),
        "settled": settled,
        "coverage": coverage,
        "settle_reasons": dict(reasons),
        "settle_sources": dict(sources),
        "unsettled": applied - settled,
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description="H2 post-measure coverage")
    ap.add_argument("--ledger", default=None, help="台账路径（默认走真源 mimir home）")
    ap.add_argument("--min-coverage", type=float, default=0.5)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    path = (Path(args.ledger) if args.ledger
            else get_mimir_home() / "data" / "compression_quality.jsonl")

    if not path.exists():
        print("FAIL: compression_quality.jsonl not found: %s" % path)
        return 2

    rows, bad = load_rows(path)
    s = analyze(rows)
    s["ledger"] = str(path)
    s["unparsable_lines"] = bad

    if args.json:
        print(json.dumps(s, ensure_ascii=False, indent=2))
        return 0 if (s["coverage"] is not None and s["coverage"] >= args.min_coverage) else 1

    print("ledger      : %s" % s["ledger"])
    print("applied     : %d" % s["applied"])
    print("post rows   : %d  (settled=%d / 未结=%d)"
          % (s["post_rows"], s["settled"], s["unsettled"]))
    print("reasons     : %s" % (s["settle_reasons"] or "{}"))
    print("sources     : %s" % (s["settle_sources"] or "{}"))
    print("coverage    : %s" % ("n/a" if s["coverage"] is None
                                else "%.4f (min=%.2f)" % (s["coverage"], args.min_coverage)))
    if bad:
        print("UNPARSABLE  : %d line(s)" % bad)
    if s["applied"] == 0:
        print("VERDICT: NO_APPLIED -- 没有 applied 行，覆盖率无从计算")
        return 1
    if s["coverage"] >= args.min_coverage:
        print("VERDICT: OK")
        return 0
    print("VERDICT: LOW -- 结算率低于下限；先看 sources 里 cross_run 是否为 0")
    return 1


if __name__ == "__main__":
    sys.exit(main())
