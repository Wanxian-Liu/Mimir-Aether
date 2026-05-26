#!/usr/bin/env python3
"""Collect Wave 6 evidence JSON + phase0 markdown (IQ-EVO-30～34)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.wave6_evidence import (  # noqa: E402
    compute_feishu_smoke_evidence,
    compute_jepa_no_candidates_rate,
    compute_nudge_counts_7d,
    compute_search_first_audit,
    write_json,
)


def _md_table_feishu(data: dict) -> str:
    lines = [
        "# IQ-EVO-30 — Feishu 3-scenario smoke evidence",
        "",
        f"- state.db: `{data.get('state_db', 'n/a')}`",
        f"- window: {data.get('days', 7)}d",
        "",
        "| Scenario | Status | Evidence |",
        "|----------|--------|----------|",
    ]
    for s in data.get("scenarios", []):
        lines.append(
            f"| {s.get('label')} | {s.get('status')} | {s.get('evidence')} |"
        )
    lines.append("")
    lines.append("> Documented fail = no matching sessions or no session_search in matched sessions.")
    return "\n".join(lines) + "\n"


def _md_table_audit(data: dict) -> str:
    lines = [
        "# IQ-EVO-31 — search-first violation audit",
        "",
        f"- sampled: {data.get('sampled')}",
        f"- violations: {data.get('violations')}",
        f"- violation_rate: {data.get('violation_rate')}",
        "",
        "| session_id | violation | user_snippet |",
        "|------------|-----------|--------------|",
    ]
    for row in data.get("rows", []):
        lines.append(
            f"| {row.get('session_id')} | {'Y' if row.get('violation') else 'N'} | {row.get('user_snippet', '')[:60]} |"
        )
    return "\n".join(lines) + "\n"


def main() -> int:
    phase0 = ROOT / "docs" / "phase0"
    phase0.mkdir(parents=True, exist_ok=True)

    smoke = compute_feishu_smoke_evidence()
    write_json(smoke, "feishu_smoke_3scenarios.json")
    (phase0 / "iqevo-30-feishu-smoke-evidence.md").write_text(
        _md_table_feishu(smoke), encoding="utf-8"
    )

    audit = compute_search_first_audit()
    write_json(audit, "search_first_audit_10.json")
    (phase0 / "iqevo-31-search-first-audit.md").write_text(
        _md_table_audit(audit), encoding="utf-8"
    )

    nudge = compute_nudge_counts_7d()
    write_json(nudge, "nudge_counts_7d.json")
    (phase0 / "iqevo-33-nudge-7d.md").write_text(
        "# IQ-EVO-33 — nudge 7d counts\n\n"
        f"- memory: {nudge.get('memory_nudge_count')}\n"
        f"- skill: {nudge.get('skill_nudge_count')}\n"
        f"- files_scanned: {nudge.get('files_scanned')}\n",
        encoding="utf-8",
    )

    jepa = compute_jepa_no_candidates_rate()
    write_json(jepa, "jepa_no_candidates_7d.json")
    (phase0 / "iqevo-34-jepa-candidate-rate.md").write_text(
        "# IQ-EVO-34 — JEPA no_candidates rate\n\n"
        f"- no_candidates: {jepa.get('no_candidates')}\n"
        f"- rate: {jepa.get('no_candidates_rate')}\n"
        f"- note: {jepa.get('trend_note')}\n",
        encoding="utf-8",
    )

    print("wrote phase0 iqevo-30/31/33/34 + data/ops/*.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
