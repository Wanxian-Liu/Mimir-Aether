#!/usr/bin/env python3
"""IQ-EVO-32: offline intent labels from feedback_events.jsonl (no production Predictor)."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mimir_constants import get_mimir_home

INTENT_RULES = (
    ("tool_failure", "recovery"),
    ("pipeline_close", "session_close"),
    ("analysis_artifact", "reflection"),
    ("tune_applied", "threshold_tune"),
)


def label_event(event: Dict[str, Any]) -> str:
    kind = str(event.get("event_type") or event.get("kind") or "")
    for needle, label in INTENT_RULES:
        if needle in kind:
            return label
    msg = json.dumps(event, ensure_ascii=False)[:500].lower()
    if "search" in msg or "session" in msg:
        return "recall"
    if "error" in msg or "fail" in msg:
        return "recovery"
    return "general"


def label_feedback_jsonl(
    path: Path,
    *,
    limit: int = 500,
) -> List[Dict[str, Any]]:
    if not path.is_file():
        return []
    out: List[Dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        out.append(
            {
                "intent_label": label_event(event),
                "event_type": event.get("event_type") or event.get("kind"),
                "session_id": event.get("session_id", ""),
            }
        )
        if len(out) >= limit:
            break
    return out


def main() -> int:
    home = get_mimir_home()
    src = home / "data" / "feedback_events.jsonl"
    labeled = label_feedback_jsonl(src)
    out_dir = home / "data" / "ops"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "intent_labels_offline.json"
    payload = {
        "source": str(src),
        "count": len(labeled),
        "labels": labeled[:20],
        "distribution": {},
    }
    dist: Dict[str, int] = {}
    for row in labeled:
        dist[row["intent_label"]] = dist.get(row["intent_label"], 0) + 1
    payload["distribution"] = dist
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(out_path)
    print("distribution:", dist)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
