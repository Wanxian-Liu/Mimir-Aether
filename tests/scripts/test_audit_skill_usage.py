import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts"))
import audit_skill_usage as asu  # noqa: E402


def test_scan_counts(tmp_path, monkeypatch):
    home = tmp_path
    (home / "logs").mkdir()
    (home / "logs" / "agent.log").write_text(
        "2026-06-01 10:00:00 skill-route nudge\n"
        "2026-06-01 10:00:01 skill_view mimiraether-self-audit\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("MIMIR_AETHER_HOME", str(home))
    out = asu.scan_logs(7)
    assert out["skill_view_7d"] >= 1
    assert out["skill_route_nudge_7d"] >= 1
