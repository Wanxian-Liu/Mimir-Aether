#!/usr/bin/env python3
"""Seed one JSONL session with OPS gateway single-instance narrative (IQ-IDX-01).

Creates ``data/sessions/ops_gateway_single_instance_anchor.jsonl`` so
``session_search`` can retrieve ``ensure_single_gateway.sh`` after backfill.
Idempotent: skips if file already exists unless ``--force``.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mimir_constants import get_mimir_home

SESSION_ID = "ops_gateway_single_instance_anchor"
ANCHOR_TEXT = (
    "OPS 记录：gateway 曾出现双实例（两个 nohup PID 同时监听 18999）。"
    "处理：使用 scripts/ensure_single_gateway.sh 杀掉旧进程并单实例重启；"
    "根因是重复 nohup gateway/run.py。验收：curl http://127.0.0.1:18999/health 仅一个 PID。"
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    home = get_mimir_home()
    out = home / "data" / "sessions" / f"{SESSION_ID}.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists() and not args.force:
        print(json.dumps({"ok": True, "skipped": True, "path": str(out)}))
        return 0

    ts = datetime.now(timezone.utc).isoformat()
    lines = [
        {
            "role": "session_meta",
            "platform": "ops",
            "model": "anchor",
            "timestamp": ts,
        },
        {"role": "user", "content": "记下 gateway 单实例运维结论", "timestamp": ts},
        {"role": "assistant", "content": ANCHOR_TEXT, "timestamp": ts},
    ]
    out.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False) for row in lines) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"ok": True, "path": str(out), "session_id": SESSION_ID}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
