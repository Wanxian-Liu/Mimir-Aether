#!/usr/bin/env python3
"""IQ-EVO-41 staging: real ~/.mimiraether/skills write via run_post_analysis_sync (path B).

Not gate-b-pilot. Requires MIMIR_AUTO_ANALYSIS=1 and MIMIR_AUTO_EVOLVE=1.
"""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

REPO = Path(__file__).resolve().parents[1]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

SKILL_NAME = "iqevo-41-gate-c-staging"
SESSION_ID = f"iqevo41-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
TASK_NAME = "iqevo-41-staging-write"
BEFORE = """# IQ-EVO-41 staging skill (before)

Gate C staging evidence target. Do not use in production workflows.
"""
AFTER_MARKER = "# IQ-EVO-41 staging skill (after apply_evolution_from_analysis)\n"


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()[:16]


def main() -> int:
    from mimir_constants import get_mimir_home, get_skills_dir
    from mimiraether_logging import setup_logging

    home = get_mimir_home()
    setup_logging(hermes_home=home, mode="cli", force=True)
    skills_dir = get_skills_dir()
    if "gate-b-pilot" in str(skills_dir):
        print("FAIL: skills_dir looks like pilot", skills_dir, file=sys.stderr)
        return 1

    skill_dir = skills_dir / SKILL_NAME
    skill_dir.mkdir(parents=True, exist_ok=True)
    skill_md = skill_dir / "SKILL.md"
    skill_md.write_text(BEFORE, encoding="utf-8")
    before_hash = _sha(skill_md)

    traj = home / "data" / "trajectories" / f"{SESSION_ID}.jsonl"
    traj.parent.mkdir(parents=True, exist_ok=True)
    traj.write_text(
        json.dumps(
            {
                "type": "session_start",
                "task_name": TASK_NAME,
                "session_id": SESSION_ID,
                "start_time": datetime.now(timezone.utc).isoformat(),
            }
        )
        + "\n",
        encoding="utf-8",
    )

    from agent.execution_pipeline import (
        close_execution_pipeline,
        start_execution_pipeline,
    )
    from agent.execution_pipeline_sessions import reset_execution_pipeline_state
    from agent.post_close_analysis import run_post_analysis_sync

    reset_execution_pipeline_state()
    start_execution_pipeline(task_name=TASK_NAME, session_id=SESSION_ID)
    pipeline_result = close_execution_pipeline(session_id=SESSION_ID)
    pipeline_result["errors"] = [
        {"tool_name": "read_file", "message": "IQ-EVO-41 controlled staging failure"}
    ]
    pipeline_result["degraded_tools"] = ["read_file"]

    analysis_payload = {
        "summary": "IQ-EVO-41 staging: apply fix to gate-c evidence skill",
        "overall_rating": 5,
        "tool_issues": ["read_file failed in controlled run"],
        "suggestions": [
            {
                "target": SKILL_NAME,
                "action": "fix",
                "reason": "IQ-EVO-41 staging write evidence",
                "priority": 1,
                "confidence": 0.95,
                "suggested_changes": AFTER_MARKER
                + "\nWritten by run_post_analysis_sync → apply_evolution_from_analysis.\n",
            }
        ],
    }
    mock_response = MagicMock()
    mock_response.choices = [
        MagicMock(message=MagicMock(content=json.dumps(analysis_payload)))
    ]

    with patch("agent.auxiliary_client.call_llm", return_value=mock_response):
        reason = run_post_analysis_sync(
            pipeline_result,
            task_name=TASK_NAME,
            session_id=SESSION_ID,
        )

    after_text = skill_md.read_text(encoding="utf-8")
    after_hash = _sha(skill_md)
    artifacts = sorted(
        (home / "data" / "analysis_artifacts").glob("*.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    artifact = artifacts[0] if artifacts else None

    out = {
        "ok": reason is None and AFTER_MARKER.strip() in after_text,
        "skip_reason": reason,
        "session_id": SESSION_ID,
        "skills_dir": str(skills_dir),
        "skill_path": str(skill_md.resolve()),
        "before_hash": before_hash,
        "after_hash": after_hash,
        "artifact": str(artifact.resolve()) if artifact else None,
        "before_preview": BEFORE.strip().splitlines()[:5],
        "after_preview": after_text.strip().splitlines()[:8],
    }
    print(json.dumps(out, indent=2, ensure_ascii=False))
    return 0 if out["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
