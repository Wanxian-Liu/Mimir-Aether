#!/usr/bin/env python3
"""CLI wrapper for IQ-EVO-29 session_search 7d baseline."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.session_search_usage_baseline import (
    compute_session_search_baseline,
    default_output_path,
    write_baseline_json,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--days", type=int, default=7)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--db", type=Path, default=None)
    args = parser.parse_args()

    if args.output:
        result = compute_session_search_baseline(days=args.days, db_path=args.db)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        payload = {**result, "output_path": str(args.output)}
    else:
        payload = write_baseline_json(days=args.days, db_path=args.db)

    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
