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

from mimir_constants import get_mimir_home

RECALL_RE = re.compile(
    r"(上次|之前|历史|还记得|继续|查一下|查历史|world model|世界模型|IR-|decision|偏好|preference)",
    re.I,
)

TOOL_CALL_RE = re.compile(r'"name"\s*:\s*"session_search"|session_search\s*\(')


@dataclass
class AuditRow:
    session_file: str
    user_snippet: str
    searched_before_answer: bool
    evidence: str


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
        while j < len(turns) and turns[j].get("role") != "user":
            chunk = json.dumps(turns[j], ensure_ascii=False)
            if TOOL_CALL_RE.search(chunk) or (
                turns[j].get("role") == "tool"
                and turns[j].get("tool_name") == "session_search"
            ):
                searched = True
                evidence = "tool session_search in turn"
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
            )
        )
        i += 1
    return out


def run_audit(*, sessions_dir: Path, limit: int = 10) -> Dict[str, Any]:
    files = sorted(
        sessions_dir.glob("*.jsonl"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    all_rows: List[AuditRow] = []
    for path in files:
        all_rows.extend(audit_session(path))
    # newest recall-like turns first (by file mtime order)
    sample = all_rows[:limit]
    violations = [r for r in sample if not r.searched_before_answer]
    rate = round(len(violations) / len(sample), 4) if sample else None
    return {
        "ok": True,
        "sessions_dir": str(sessions_dir),
        "recall_candidates_total": len(all_rows),
        "sample_size": len(sample),
        "violations": len(violations),
        "violation_rate": rate,
        "rows": [
            {
                "session_file": r.session_file,
                "user_snippet": r.user_snippet,
                "search_first_ok": r.searched_before_answer,
                "evidence": r.evidence,
            }
            for r in sample
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
