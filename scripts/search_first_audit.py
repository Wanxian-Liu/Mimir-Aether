#!/usr/bin/env python3
"""IQ-EVO-31 / Gate A3: search-first violation audit from session JSONL."""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent.search_first_guard import (
    EXPLICIT_CROSS_SESSION_RE,
    RECALL_RE,
    exclude_user_message,
)
from mimir_constants import get_mimir_home

TOOL_CALL_RE = re.compile(r'"name"\s*:\s*"session_search"|session_search\s*\(')
_SEARCH_FIRST_MARKER = "[search-first-guard]"
_PREEMPTIVE_MARKER = "[SEARCH-FIRST-RESULTS]"


@dataclass
class AuditRow:
    session_file: str
    user_snippet: str
    searched_before_answer: bool
    evidence: str
    exclude_reason: str = ""

    @property
    def filtered_in_scope(self) -> bool:
        return not self.exclude_reason


def exclude_reason(content: str) -> str:
    """False-positive classes excluded from filtered violation rate (WA-A06)."""
    return exclude_user_message(content)


def _load_turns(path: Path) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def audit_session(path: Path) -> List[AuditRow]:
    turns = _load_turns(path)
    out: List[AuditRow] = []
    i = 0
    while i < len(turns):
        row = turns[i]
        if row.get("role") != "user":
            i += 1
            continue
        content = (row.get("content") or "").strip()
        if not content or not RECALL_RE.search(content):
            i += 1
            continue
        snippet = content[:120].replace("\n", " ")
        searched = False
        evidence = ""
        j = i + 1
        while j < len(turns) and (
            turns[j].get("role") != "user"
            or str(turns[j].get("content", "")).strip().startswith(_SEARCH_FIRST_MARKER)
            or str(turns[j].get("content", "")).strip().startswith(_PREEMPTIVE_MARKER)
        ):
            chunk = json.dumps(turns[j], ensure_ascii=False)
            if TOOL_CALL_RE.search(chunk) or (
                turns[j].get("role") == "tool"
                and turns[j].get("tool_name") == "session_search"
            ):
                searched = True
                evidence = "tool session_search in turn"
                break
            if str(turns[j].get("content", "")).strip().startswith(_PREEMPTIVE_MARKER):
                searched = True
                evidence = "preemptive session_search"
                break
            if turns[j].get("role") == "assistant":
                ac = (turns[j].get("content") or "")
                if "session_search" in ac and (
                    "找到了" in ac or "搜索结果" in ac or "Session" in ac or "命中" in ac
                ):
                    searched = True
                    evidence = "assistant cites session_search results"
                    break
            j += 1
        out.append(
            AuditRow(
                session_file=path.name,
                user_snippet=snippet,
                searched_before_answer=searched,
                evidence=evidence or "no session_search before next user turn",
                exclude_reason=exclude_reason(content),
            )
        )
        i += 1
    return out


def _violation_rate(rows: List[AuditRow]) -> Optional[float]:
    if not rows:
        return None
    violations = sum(1 for r in rows if not r.searched_before_answer)
    return round(violations / len(rows), 4)


def run_audit(*, sessions_dir: Path, limit: int = 10) -> Dict[str, Any]:
    files = sorted(
        sessions_dir.glob("*.jsonl"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    all_rows: List[AuditRow] = []
    for path in files:
        all_rows.extend(audit_session(path))
    sample = all_rows[:limit]
    filtered_rows = [r for r in all_rows if r.filtered_in_scope]
    filtered_sample = filtered_rows[:limit]
    return {
        "ok": True,
        "sessions_dir": str(sessions_dir),
        "recall_candidates_total": len(all_rows),
        "sample_size": len(sample),
        "violations": sum(1 for r in sample if not r.searched_before_answer),
        "violation_rate": _violation_rate(sample),
        "filtered_recall_candidates_total": len(filtered_rows),
        "filtered_sample_size": len(filtered_sample),
        "filtered_violations": sum(
            1 for r in filtered_sample if not r.searched_before_answer
        ),
        "filtered_violation_rate": _violation_rate(filtered_sample),
        "rows": [
            {
                "session_file": r.session_file,
                "user_snippet": r.user_snippet,
                "search_first_ok": r.searched_before_answer,
                "evidence": r.evidence,
                "exclude_reason": r.exclude_reason or None,
                "filtered_in_scope": r.filtered_in_scope,
            }
            for r in sample
        ],
        "filtered_rows": [
            {
                "session_file": r.session_file,
                "user_snippet": r.user_snippet,
                "search_first_ok": r.searched_before_answer,
                "evidence": r.evidence,
                "exclude_reason": r.exclude_reason or None,
                "filtered_in_scope": r.filtered_in_scope,
            }
            for r in filtered_sample
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    sessions_dir = get_mimir_home() / "data" / "sessions"
    result = run_audit(sessions_dir=sessions_dir, limit=args.limit)
    out_path = args.output or (
        ROOT / "docs" / "phase0" / "iqevo-31-search-first-audit.json"
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({**result, "output_path": str(out_path)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
