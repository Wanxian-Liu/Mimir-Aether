"""IQ-EVO-32 offline intent labeling."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from label_intent_offline import label_event, label_feedback_jsonl  # noqa: E402


def test_label_event_kinds():
    assert label_event({"event_type": "analysis_artifact"}) == "reflection"
    assert label_event({"event_type": "pipeline_close"}) == "session_close"


def test_label_feedback_jsonl(tmp_path):
    p = tmp_path / "feedback_events.jsonl"
    p.write_text(
        json.dumps({"event_type": "tool_failure", "session_id": "a"}) + "\n",
        encoding="utf-8",
    )
    rows = label_feedback_jsonl(p)
    assert rows[0]["intent_label"] == "recovery"
