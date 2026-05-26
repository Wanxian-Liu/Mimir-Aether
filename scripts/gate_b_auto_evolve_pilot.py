#!/usr/bin/env python3
"""Gate B2/B3: five pipeline closes with suggestions + AUTO_EVOLVE apply (isolated skills)."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mimir_constants import get_mimir_home


def _one_close(
    *,
    skills_dir: Path,
    run_id: int,
    monkeypatch_env: bool,
) -> dict:
    if monkeypatch_env:
        os.environ["MIMIR_AETHER_HOME"] = str(skills_dir.parent)
        os.environ["MIMIR_AUTO_EVOLVE"] = "1"

    from agent.execution_pipeline import (
        apply_analysis_to_pipeline,
        close_execution_pipeline,
        schedule_post_close_evolution,
        start_execution_pipeline,
    )
    from agent.execution_pipeline_sessions import reset_execution_pipeline_state

    reset_execution_pipeline_state()
    skill_name = f"gate-b-pilot-{run_id}"
    skill_dir = skills_dir / skill_name
    skill_dir.mkdir(parents=True, exist_ok=True)
    (skill_dir / "SKILL.md").write_text(f"# before {run_id}\n", encoding="utf-8")

    sid = f"gate-b-sess-{run_id}"
    start_execution_pipeline(task_name=f"gate-b-{run_id}", session_id=sid)

    analysis_json = json.dumps(
        {
            "summary": f"synthetic tool failure run {run_id}",
            "suggestions": [
                {
                    "target": skill_name,
                    "action": "fix",
                    "reason": "gate B pilot",
                    "suggested_changes": f"# after gate-b {run_id}\n",
                    "priority": 1,
                    "confidence": 0.9,
                }
            ],
        }
    )
    apply_analysis_to_pipeline(analysis_json, session_id=sid, task_name=f"gate-b-{run_id}")
    result = close_execution_pipeline(session_id=sid)
    had_suggestions = bool(result.get("_evolution_suggestion_objs"))
    schedule_post_close_evolution(result, skills_dir=skills_dir)

    after = (skill_dir / "SKILL.md").read_text(encoding="utf-8")
    evo = result.get("evolution_results") or []
    return {
        "run_id": run_id,
        "session_id": sid,
        "had_suggestions": had_suggestions,
        "evolution_results": evo,
        "skill_written": f"# after gate-b {run_id}" in after,
        "skill_path": str(skill_dir / "SKILL.md"),
    }


def main() -> int:
    os.environ.setdefault("MIMIR_AUTO_EVOLVE", "1")
    home = get_mimir_home()
    pilot_root = home / "data" / "ops" / "gate-b-pilot"
    skills_dir = pilot_root / "skills"
    skills_dir.mkdir(parents=True, exist_ok=True)

    rows = []
    for i in range(1, 6):
        rows.append(_one_close(skills_dir=skills_dir, run_id=i, monkeypatch_env=False))

    writes = sum(1 for r in rows if r["skill_written"])
    with_suggestions = sum(1 for r in rows if r["had_suggestions"])
    evo_ok = sum(1 for r in rows if r["evolution_results"])

    out = {
        "ok": with_suggestions >= 5 and writes >= 1 and evo_ok >= 5,
        "closes": 5,
        "with_suggestions": with_suggestions,
        "skill_writes": writes,
        "skills_dir": str(skills_dir),
        "runs": rows,
        "gate_b2": with_suggestions >= 5,
        "gate_b3": with_suggestions >= 3 and writes >= 1 and evo_ok >= 5,
    }
    out_path = pilot_root / "gate-b-pilot-evidence.json"
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({**out, "output_path": str(out_path)}, ensure_ascii=False, indent=2))
    return 0 if out["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
