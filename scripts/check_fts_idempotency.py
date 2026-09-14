#!/usr/bin/env python3
"""RS20（§29 Q16 · 2026-09-14）幂等性检查 —— "批写入行数 vs distinct hash"。

RS19 统一检查清单的候选检查项之一（形态：只读 + 一行 VERDICT + 非零退出码）。

    python3 scripts/check_fts_idempotency.py            # 默认生产库
    python3 scripts/check_fts_idempotency.py --db PATH

退出码：0 = PASS · 1 = FAIL（重复/失同步/机制未生效）· 2 = 库不存在。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.fts5_search.integrity import check_fts_integrity, format_report

DEFAULT_DB = Path.home() / ".mimiraether" / "data" / "fts5_search.db"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    args = parser.parse_args()

    if not args.db.exists():
        print(f"FAIL db_missing: {args.db}")
        return 2
    report = check_fts_integrity(args.db)
    print(format_report(report))
    return 0 if report["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
