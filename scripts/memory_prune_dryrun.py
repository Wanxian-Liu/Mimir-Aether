#!/usr/bin/env python3
"""L5 · S2' 遗忘 dry-run（2026-10-13 · 会议卡 §B「遗忘」）。

**只读 · 只打印候选清单与条数 · 绝不改盘。**

候选判据（保守阈值，逐字来自会议卡 §B S2' 前置③）:
  θ_importance = 5  ∧  age >= 90 天  ∧  maturity == 'draft'
age = 今天 − last_access（缺失时回落 created_at；两者皆无 ⇒ 不计候选，
单独计入 skipped_no_timestamp —— 不猜年龄）。

rc 语义：0=读数成功（**包括 candidates=0**，dry-run 不把「没候选」当失败）
        2=找不到 persistent.json
        3=MIMIR_MEMORY_PRUNE=apply —— **本步未接真删（gated）**，明确拒绝

**真删为什么没接**：会议卡 §B S2'「真删开关 gated 在 S1′ 判据为正 ∧ 连续 2
周期 dry-run 稳定」。今天 S1′ 判据为红（importance<50=0/49），故开关不接：
本脚本在任何情况下都不会删条目、不会写 archive.jsonl。archive 面
（data/persistent.archive.jsonl）已建为空文件，等 gate 打开后由真删路径 append。

用法（复核方直接重跑）:
  ~/src/MimirAether/.venv/bin/python3 scripts/memory_prune_dryrun.py
  ~/src/MimirAether/.venv/bin/python3 scripts/memory_prune_dryrun.py --path <副本>
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import pathlib
import sys

SCAN_KEYS = ("key_decisions", "learned_patterns")
THETA_IMPORTANCE = 5
MIN_AGE_DAYS = 90
REQUIRED_MATURITY = "draft"
APPLY_ENV = "MIMIR_MEMORY_PRUNE"


def default_path() -> pathlib.Path:
    home = os.environ.get("MIMIR_AETHER_HOME") or os.path.expanduser("~/.mimiraether")
    return pathlib.Path(home) / "data" / "persistent.json"


def archive_path() -> pathlib.Path:
    home = os.environ.get("MIMIR_AETHER_HOME") or os.path.expanduser("~/.mimiraether")
    return pathlib.Path(home) / "data" / "persistent.archive.jsonl"


def _age_days(entry: dict, now: datetime.datetime) -> int | None:
    for field in ("last_access", "created_at"):
        ts = entry.get(field)
        if isinstance(ts, str) and ts:
            try:
                parsed = datetime.datetime.fromisoformat(ts)
            except ValueError:
                continue
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=datetime.timezone.utc)
            return max(0, (now - parsed).days)
    return None


def _label(entry: dict) -> str:
    for field in ("decision", "pattern"):
        v = entry.get(field)
        if isinstance(v, str) and v:
            return v[:60]
    return "<no decision/pattern field>"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="L5 S2' forget dry-run (read-only)")
    ap.add_argument("--path", default=None, help="persistent.json 路径（自测/负控用副本）")
    ap.add_argument("--json", action="store_true", help="输出 JSON")
    args = ap.parse_args(argv)

    mode = (os.environ.get(APPLY_ENV) or "").strip().lower()

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
    memory = data.get("memory") if isinstance(data.get("memory"), dict) else {}

    scanned = 0
    skipped_no_timestamp = 0
    candidates: list[dict] = []
    per_key: dict[str, int] = {}
    for key in SCAN_KEYS:
        rows = memory.get(key)
        rows = rows if isinstance(rows, list) else []
        per_key[key] = sum(1 for e in rows if isinstance(e, dict))
        for idx, entry in enumerate(rows):
            if not isinstance(entry, dict):
                continue
            scanned += 1
            age = _age_days(entry, now)
            if age is None:
                skipped_no_timestamp += 1
                continue
            importance = entry.get("importance")
            maturity = entry.get("maturity")
            if (
                isinstance(importance, int)
                and importance <= THETA_IMPORTANCE
                and age >= MIN_AGE_DAYS
                and maturity == REQUIRED_MATURITY
            ):
                candidates.append(
                    {
                        "key": key,
                        "index": idx,
                        "importance": importance,
                        "age_days": age,
                        "maturity": maturity,
                        "idle_since": entry.get("last_access") or entry.get("created_at"),
                        "label": _label(entry),
                    }
                )

    if args.json:
        print(json.dumps({
            "path": str(path),
            "scanned": scanned,
            "per_key": per_key,
            "skipped_no_timestamp": skipped_no_timestamp,
            "candidates": len(candidates),
            "candidate_rows": candidates,
            "thresholds": {
                "theta_importance": THETA_IMPORTANCE,
                "min_age_days": MIN_AGE_DAYS,
                "maturity": REQUIRED_MATURITY,
            },
            "apply_switch": mode or "unset",
            "wrote": False,
        }, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(f"path={path} bytes={path.stat().st_size}")
        print(f"scanned={scanned} (key_decisions={per_key.get('key_decisions', 0)} "
              f"learned_patterns={per_key.get('learned_patterns', 0)})")
        print(f"thresholds: importance<={THETA_IMPORTANCE} AND age>={MIN_AGE_DAYS}d AND maturity=='{REQUIRED_MATURITY}'")
        print(f"skipped_no_timestamp={skipped_no_timestamp}")
        print(f"candidates={len(candidates)}")
        for c in candidates:
            print(f"  - {c['key']}[{c['index']}] importance={c['importance']} age_days={c['age_days']} "
                  f"maturity={c['maturity']} idle_since={c['idle_since']} :: {c['label']}")
        print(f"archive_surface={archive_path()} exists={archive_path().exists()} "
              f"bytes={(archive_path().stat().st_size if archive_path().exists() else 0)}")
        print(f"apply_switch={mode or 'unset'}")
        print("WRITE=NONE (dry-run: this script never modifies persistent.json or the archive)")

    if mode == "apply":
        print(
            "REFUSED: MIMIR_MEMORY_PRUNE=apply is gated and NOT implemented in this step.\n"
            "  gate = (S1' 判据为正) AND (连续 2 周期 dry-run 输出稳定)\n"
            "  today: S1' 判据为红 (importance<50=0/49) ⇒ 真删不接（防「造一个永远报 0 的遗忘器」）"
        )
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
