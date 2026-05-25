#!/usr/bin/env python3
"""Compare memory retrieval benchmark JSON against a frozen baseline (IEVO-04)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict

DEFAULT_MIN_LIKE_FLOOR = 0.50
DEFAULT_LIKE_REGRESSION_DELTA = 0.05
DEFAULT_SEMANTIC_REGRESSION_DELTA = 0.05


def compare_memory_retrieval_report(
    current: Dict[str, Any],
    baseline: Dict[str, Any],
    *,
    min_like_floor: float = DEFAULT_MIN_LIKE_FLOOR,
    like_regression_delta: float = DEFAULT_LIKE_REGRESSION_DELTA,
    semantic_regression_delta: float = DEFAULT_SEMANTIC_REGRESSION_DELTA,
) -> Dict[str, Any]:
    """Return comparison dict with ``pass`` bool and metric deltas."""
    cur_like = float(current.get("like_hit_rate") or 0)
    cur_fts = float(current.get("fts_hit_rate") or 0)
    base_like = float(baseline.get("like_hit_rate") or 0)
    base_fts = float(baseline.get("fts_hit_rate") or 0)

    min_like = max(min_like_floor, base_like - like_regression_delta)
    like_ok = cur_like >= min_like
    fts_ok = cur_fts >= (base_fts - like_regression_delta) if baseline.get("fts_db") else True

    base_sem_raw = baseline.get("semantic_hit_rate")
    cur_sem_raw = current.get("semantic_hit_rate")
    semantic_skipped = base_sem_raw is None
    if semantic_skipped:
        semantic_ok = True
        min_sem = None
        cur_sem = float(cur_sem_raw) if cur_sem_raw is not None else None
        base_sem = None
    elif cur_sem_raw is None:
        semantic_ok = False
        min_sem = max(0.0, float(base_sem_raw) - semantic_regression_delta)
        cur_sem = None
        base_sem = float(base_sem_raw)
    else:
        base_sem = float(base_sem_raw)
        cur_sem = float(cur_sem_raw)
        min_sem = max(0.0, base_sem - semantic_regression_delta)
        semantic_ok = cur_sem >= min_sem

    return {
        "pass": like_ok and fts_ok and semantic_ok,
        "like_hit_rate": {"current": cur_like, "baseline": base_like, "min_allowed": min_like, "ok": like_ok},
        "fts_hit_rate": {"current": cur_fts, "baseline": base_fts, "ok": fts_ok},
        "semantic_hit_rate": {
            "current": cur_sem,
            "baseline": base_sem,
            "min_allowed": min_sem,
            "ok": semantic_ok,
            "skipped": semantic_skipped,
        },
        "queries": {"current": current.get("queries"), "baseline": baseline.get("queries")},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("current", type=Path, help="Fresh benchmark JSON from run_memory_retrieval_benchmark.py")
    parser.add_argument(
        "--baseline",
        type=Path,
        default=Path(__file__).resolve().parents[1]
        / "docs/phase0/memory-retrieval-benchmark-20260524.json",
    )
    parser.add_argument("--json-out", type=Path, default=None, help="Write comparison summary JSON")
    args = parser.parse_args()

    current = json.loads(args.current.read_text(encoding="utf-8"))
    baseline = json.loads(args.baseline.read_text(encoding="utf-8"))
    summary = compare_memory_retrieval_report(current, baseline)

    print(json.dumps(summary, indent=2, ensure_ascii=False))
    if args.json_out:
        args.json_out.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"Wrote {args.json_out}", file=sys.stderr)

    return 0 if summary["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
