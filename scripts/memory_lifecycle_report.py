#!/usr/bin/env python3
"""L5 · S1' 生命周期只读报告（2026-10-13 · 会议卡 §B「管」）。

作用：把「importance 是不是真信号」变成可复算读数 —— 报告 kd/lp 的
  importance<50 条数 / 总数  与  distinct(last_access) 个数。

判据（能红 · 正控，两向）:
  A  importance<50 > 0        （分数真的掉下来了 = 衰减真的跑过）
  B  distinct(last_access) > 1（时间戳不是同一个时钟批量刷的 = 条目有各自龄）
rc 语义：0=两条件皆过 / 1=任一未过 / 2=找不到 persistent.json

**只读**：本脚本只 json.load，永不写盘（判据里「主件条数不变」靠本约束）。
只扫 memory.key_decisions / memory.learned_patterns（AKL 4 字段目前的覆盖面，
见会议卡 F6：behavioral_constraints / active_projects 无 lifecycle 字段）。

用法（复核方直接重跑）:
  ~/src/MimirAether/.venv/bin/python3 scripts/memory_lifecycle_report.py
  ~/src/MimirAether/.venv/bin/python3 scripts/memory_lifecycle_report.py --path <副本> [--json]
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

SCAN_KEYS = ("key_decisions", "learned_patterns")
LOW_IMPORTANCE = 50


def default_path() -> pathlib.Path:
    home = os.environ.get("MIMIR_AETHER_HOME") or os.path.expanduser("~/.mimiraether")
    return pathlib.Path(home) / "data" / "persistent.json"


def _age_days(ts: object, now: datetime.datetime) -> int | None:
    if not isinstance(ts, str) or not ts:
        return None
    try:
        parsed = datetime.datetime.fromisoformat(ts)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=datetime.timezone.utc)
    return max(0, (now - parsed).days)


def scan(data: dict, now: datetime.datetime) -> dict:
    memory = data.get("memory") if isinstance(data.get("memory"), dict) else {}
    per_key: dict[str, dict] = {}
    total_n = total_low = 0
    all_last_access: list[object] = []
    for key in SCAN_KEYS:
        rows = memory.get(key)
        rows = rows if isinstance(rows, list) else []
        dicts = [e for e in rows if isinstance(e, dict)]
        imps = [e.get("importance") for e in dicts]
        last = [e.get("last_access") for e in dicts]
        low = sum(1 for i in imps if isinstance(i, int) and i < LOW_IMPORTANCE)
        created = sum(1 for e in dicts if e.get("created_at"))
        acc = sum(1 for e in dicts if isinstance(e.get("access_count"), int))
        ages = [a for a in (_age_days(t, now) for t in last) if a is not None]
        per_key[key] = {
            "n": len(dicts),
            "importance_lt_50": low,
            "created_at_present": created,
            "access_count_present": acc,
            "distinct_last_access": len(set(last)),
            "importance_min": min([i for i in imps if isinstance(i, int)], default=None),
            "importance_max": max([i for i in imps if isinstance(i, int)], default=None),
            "age_days_max": max(ages, default=None),
        }
        total_n += len(dicts)
        total_low += low
        all_last_access.extend(last)
    return {
        "per_key": per_key,
        "total_n": total_n,
        "total_low": total_low,
        "distinct_last_access": len(set(all_last_access)),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="L5 S1' lifecycle read-only report")
    ap.add_argument("--path", default=None, help="persistent.json 路径（自测/负控用副本）")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    args = ap.parse_args(argv)

    path = pathlib.Path(args.path) if args.path else default_path()
    if not path.is_file():
        print(f"FAIL: persistent.json not found: {path}")
        return 2

    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError) as e:
        print(f"FAIL: cannot read {path}: {e}")
        return 2

    now = datetime.datetime.now(datetime.timezone.utc)
    rep = scan(data, now)
    cond_a = rep["total_low"] > 0
    cond_b = rep["distinct_last_access"] > 1
    rep["cond_a_importance_lt_50_gt_0"] = cond_a
    rep["cond_b_distinct_last_access_gt_1"] = cond_b
    rep["verdict"] = "GREEN" if (cond_a and cond_b) else "RED"

    if args.json:
        print(json.dumps(rep, ensure_ascii=False, indent=2, sort_keys=True))
        return 0 if (cond_a and cond_b) else 1

    print(f"path={path} bytes={path.stat().st_size} mtime={datetime.datetime.fromtimestamp(path.stat().st_mtime).isoformat()}")
    for key, v in rep["per_key"].items():
        print(
            f"{key}: n={v['n']} importance<50={v['importance_lt_50']}/{v['n']} "
            f"created_at_present={v['created_at_present']}/{v['n']} "
            f"access_count_present={v['access_count_present']}/{v['n']} "
            f"distinct(last_access)={v['distinct_last_access']} "
            f"importance[min,max]=[{v['importance_min']},{v['importance_max']}] "
            f"age_days_max={v['age_days_max']}"
        )
    print(f"TOTAL entries={rep['total_n']} importance<50={rep['total_low']}/{rep['total_n']} "
          f"distinct(last_access)={rep['distinct_last_access']}")
    print(f"[A] importance<50 > 0        -> {rep['total_low']}/{rep['total_n']}   {'PASS' if cond_a else 'FAIL'}")
    print(f"[B] distinct(last_access) > 1 -> {rep['distinct_last_access']}   {'PASS' if cond_b else 'FAIL'}")
    print(f"VERDICT: {rep['verdict']}")
    return 0 if (cond_a and cond_b) else 1


if __name__ == "__main__":
    sys.exit(main())
