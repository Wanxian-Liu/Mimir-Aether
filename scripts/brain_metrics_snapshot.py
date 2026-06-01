#!/usr/bin/env python3
"""Aggregate brain metrics → data/ops/brain-metrics-latest.json."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import urllib.request
from pathlib import Path
from typing import Any, Dict

_FAKE = frozenset({"crash_tool", "orphan_tool"})


def _home() -> Path:
    return Path(
        os.environ.get("MIMIR_AETHER_HOME")
        or os.environ.get("HERMES_HOME")
        or Path.home() / ".mimiraether"
    )


def _repo() -> Path:
    return Path(os.environ.get("MIMIR_REPO_ROOT", Path(__file__).resolve().parents[1]))


def _health(port: int = 18999) -> Dict[str, Any]:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=5) as r:
            return json.loads(r.read().decode())
    except Exception as e:
        return {"status": "error", "error": str(e)}


def _monitor(home: Path) -> Dict[str, Any]:
    path = home / "data" / "monitor_alerts.json"
    if not path.is_file():
        return {"total": 0, "real": 0, "fake_positive": 0, "real_error_rate": 0.0}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"total": 0, "real": 0, "fake_positive": 0, "real_error_rate": 0.0}
    alerts = raw if isinstance(raw, list) else raw.get("alerts", [])
    fake = real = 0
    by_tool: Dict[str, int] = {}
    for a in alerts:
        if not isinstance(a, dict):
            continue
        tool = str(a.get("tool_name") or a.get("tool") or "unknown")
        by_tool[tool] = by_tool.get(tool, 0) + 1
        if tool in _FAKE:
            fake += 1
        else:
            real += 1
    total = fake + real
    return {
        "total": total,
        "fake_positive": fake,
        "real": real,
        "real_error_rate": round(real / total, 4) if total else 0.0,
        "by_tool": by_tool,
    }


def _sub(script: Path, home: Path) -> Dict[str, Any]:
    if not script.is_file():
        return {"error": f"missing {script.name}"}
    env = {**os.environ, "MIMIR_AETHER_HOME": str(home)}
    p = subprocess.run(
        [sys.executable, str(script)],
        cwd=str(_repo()),
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )
    if p.returncode != 0:
        return {"error": (p.stderr or p.stdout or "")[-500:]}
    try:
        return json.loads(p.stdout.strip().splitlines()[-1])
    except (json.JSONDecodeError, IndexError):
        return {"stdout": p.stdout[-1000:]}


def main() -> int:
    home = _home()
    repo = _repo()
    payload = {
        "health": _health(int(os.environ.get("MIMIR_PORT", "18999"))),
        "monitor_alerts": _monitor(home),
        "skill_usage": _sub(repo / "scripts" / "audit_skill_usage.py", home),
        "evolution_ok": _sub(repo / "scripts" / "iq_p3_evolution_ok_baseline.py", home),
        "env": {
            "MIMIR_FEEDBACK_COLLECTOR": os.environ.get("MIMIR_FEEDBACK_COLLECTOR", ""),
            "MIMIR_AUTO_EVOLVE": os.environ.get("MIMIR_AUTO_EVOLVE", ""),
            "MIMIR_SKILL_ROUTE_NUDGE": os.environ.get("MIMIR_SKILL_ROUTE_NUDGE", "1"),
        },
    }
    out = home / "data" / "ops" / "brain-metrics-latest.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"ok": True, "path": str(out)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
