#!/usr/bin/env python3
"""Capture a point-in-time snapshot of agent brain metrics.

Outputs to stdout (JSON) and optionally writes to data/ops/brain-metrics-latest.json.
"""

import json
import os
import re
import sqlite3
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

MIMIR_HOME = Path(os.environ.get("MIMIR_AETHER_HOME", "~/.mimiraether")).expanduser()
PERSISTENT = MIMIR_HOME / "data" / "persistent.json"
OPS_DIR = MIMIR_HOME / "data" / "ops"
AGENT_LOG = MIMIR_HOME / "logs" / "agent.log"
TOOL_QUALITY_DB = MIMIR_HOME / "data" / "tool_quality.db"


def read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return {}


def get_persistent_metrics() -> dict:
    data = read_json(PERSISTENT)
    return {
        "session_count": data.get("session_count", 0),
        "skill_usage_count": len(data.get("skill_usage", {})),
        "memory_entries": len(data.get("memory", {})) if isinstance(data.get("memory"), dict) else 0,
        "user_memory_entries": len(data.get("user", {})) if isinstance(data.get("user"), dict) else 0,
        "key_decisions_count": len(data.get("key_decisions", [])),
        "completed_milestones_count": len(data.get("completed_milestones", [])),
    }


def get_evolution_metrics() -> dict:
    baseline = read_json(OPS_DIR / "iq-p3-baseline.json")
    evo_7d = baseline.get("evolution_7d", {})
    evo_all = baseline.get("evolution_7d_including_tests", {})
    return {
        "ok_pct_7d": evo_7d.get("ok_pct", None),
        "ok_lines_7d": evo_7d.get("ok_lines", 0),
        "total_lines_7d": evo_7d.get("lines", 0),
        "unique_sessions_7d": evo_7d.get("unique_sessions", 0),
        "ok_pct_all": evo_all.get("ok_pct", None),
        "baseline_generated_at": baseline.get("generated_at", None),
    }


def get_context_metrics() -> dict:
    ctx = read_json(OPS_DIR / "last_context_usage.json")
    return {
        "prompt_tokens": ctx.get("prompt_tokens"),
        "total_tokens": ctx.get("total_tokens"),
        "message_count": ctx.get("message_count"),
        "threshold_tokens": ctx.get("threshold_tokens"),
        "model": ctx.get("model", "unknown"),
    }


def get_tool_quality_metrics() -> dict:
    if not TOOL_QUALITY_DB.is_file():
        return {"error": "tool_quality.db not found"}
    try:
        conn = sqlite3.connect(str(TOOL_QUALITY_DB))
        cur = conn.execute(
            "SELECT tool_name, CAST(success_count AS REAL) / MAX(total_calls, 1) AS rate "
            "FROM tool_quality ORDER BY total_calls DESC LIMIT 10"
        )
        top_by_calls = [{"tool": r[0], "success_rate": r[1]} for r in cur.fetchall()]
        conn.close()
        return {"top_tools_by_calls": top_by_calls}
    except sqlite3.Error as e:
        return {"error": str(e)}


def get_log_evolution_count() -> dict:
    """Count evolution ok=0 vs ok=1 lines in agent.log (recent 14d)."""
    if not AGENT_LOG.is_file():
        return {"error": "agent.log not found"}
    try:
        text = AGENT_LOG.read_text(encoding="utf-8", errors="replace")
        lines = text.splitlines()
        evo_lines = [l for l in lines if "post_analysis evolution" in l]
        ok_count = sum(1 for l in evo_lines if " ok=1" in l)
        fail_count = sum(1 for l in evo_lines if " ok=0" in l)
        return {
            "evolution_lines_total": len(evo_lines),
            "ok_count": ok_count,
            "fail_count": fail_count,
            "ok_pct": round(ok_count / max(len(evo_lines), 1) * 100, 1),
            "log_tail_lines": len(lines),
        }
    except OSError as e:
        return {"error": str(e)}


def snapshot(out_path: Path = OPS_DIR / "brain-metrics-latest.json") -> dict:
    result = {
        "generated_at": time.time(),
        "timestamp_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "persistent": get_persistent_metrics(),
        "evolution": get_evolution_metrics(),
        "evolution_log": get_log_evolution_count(),
        "context": get_context_metrics(),
        "tool_quality": get_tool_quality_metrics(),
    }

    # Write to file
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n")

    return result


if __name__ == "__main__":
    data = snapshot()

    # Print summary
    p = data["persistent"]
    e = data["evolution"]
    el = data["evolution_log"]
    ctx = data["context"]

    print(f"{'='*55}")
    print(f"  Brain Metrics Snapshot")
    print(f"  {data['timestamp_utc']}")
    print(f"{'='*55}")
    print(f"\n📊 Persistent")
    print(f"  Session count:          {p['session_count']}")
    print(f"  Skill usage tracked:    {p['skill_usage_count']}")
    print(f"  Memory entries:         {p['memory_entries']}")
    print(f"  Key decisions:          {p['key_decisions_count']}")
    print(f"  Completed milestones:   {p['completed_milestones_count']}")

    print(f"\n🧠 Evolution")
    print(f"  ok% (7d, test excl):    {e['ok_pct_7d']}%")
    print(f"  ok lines / total:       {e['ok_lines_7d']}/{e['total_lines_7d']}")
    print(f"  Unique sessions:        {e['unique_sessions_7d']}")

    print(f"\n📝 Evolution Log (all time)")
    print(f"  ok / fail / total:      {el['ok_count']}/{el['fail_count']}/{el['evolution_lines_total']}")
    print(f"  ok% (log):              {el['ok_pct']}%")

    print(f"\n💻 Context (last known)")
    print(f"  Prompt tokens:          {ctx['prompt_tokens']}")
    print(f"  Total tokens:           {ctx['total_tokens']}")
    print(f"  Messages:               {ctx['message_count']}")
    print(f"  Model:                  {ctx['model']}")

    print(f"\n🔧 Tool Quality (top 5 by calls)")
    tq = data.get("tool_quality", {})
    if "error" in tq:
        print(f"  Error: {tq['error']}")
    else:
        for t in tq.get("top_tools_by_calls", [])[:5]:
            print(f"  {t['success_rate']*100:5.1f}%  {t['tool']}")

    print(f"\nSaved: {OPS_DIR / 'brain-metrics-latest.json'}")
