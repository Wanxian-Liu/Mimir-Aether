#!/usr/bin/env python3
"""Reusable: audit session logs for search-first violations.
Target: filtered violation rate ≤40% (HC-03 / IQ55-10e).

Usage: python3 docs/phase0/search_first_audit.py [--sample 10] [--days 7]
"""

import json, os, re, sys, time
from datetime import datetime, timedelta, timezone
from pathlib import Path

SESSIONS_DIR = Path.home() / ".mimiraether" / "data" / "sessions"
MARKER = "[SEARCH-FIRST-RESULTS]"  # matches current agent_loop injection

# Cross-session trigger patterns — aligned with search_first_guard.py
CROSS_SESSION_RE = re.compile(
    r"(刚才(?!聊|说|放|的理解)|"
    r"上次|"
    r"之前(?:聊|说|做|提到|发|的|设计|决定|任务|会话|对话)?|"
    r"前一段时间|"
    r"过去|"
    r"以前|"
    r"最初的|"
    r"最开始|"
    r"旧的|"
    r"老的|"
    r"最初设计|"
    r"历史上|"
    r"传统上|"
    r"以前说过|"
    r"历史(?!数据|记录|日志|文件)|"
    r"跨(?:会话|对话)|"
    r"上一(?:轮|次|个|条)|"
    r"曾经|"
    r"最早)",
    re.IGNORECASE,
)

# Exclude patterns — things that look like cross-session but aren't
EXCLUDE_RE = re.compile(
    r"(上次你说过什么|"       # meta-reflection
    r"之前你说.*我就.*|"       # quoting the agent's own prior turn
    r"刚才聊|刚才说|刚才放|"
    r"刚才的理解|"
    r"之前理解)",
    re.IGNORECASE,
)

def collect_sessions(sessions_dir: Path, days_back: int = 7) -> list[Path]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=days_back)
    files = sorted(sessions_dir.glob("*.jsonl"), reverse=True)
    return [f for f in files if datetime.fromtimestamp(f.stat().st_mtime, tz=timezone.utc) > cutoff]


def sample_sessions(files: list[Path], sample_size: int = 10) -> list[Path]:
    if len(files) <= sample_size:
        return files
    # spread across sessions for diversity
    step = max(1, len(files) // sample_size)
    return files[::step][:sample_size]


def user_turns_in_session(session_file: Path) -> list[dict]:
    """Extract user messages from a session JSONL file, preserving order."""
    turns = []
    with open(session_file) as f:
        for line in f:
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                continue
            role = msg.get("role", "")
            if role == "user":
                content = msg.get("content", "")
                if content and isinstance(content, str) and len(content.strip()) > 10:
                    turns.append({
                        "session": session_file.name,
                        "content": content.strip()[:200],
                        "full_content": content.strip(),
                    })
    return turns


def cross_session_user_turns(turns: list[dict]) -> list[dict]:
    """Filter user turns that contain cross-session references."""
    candidates = []
    for t in turns:
        content = t["full_content"]
        if not CROSS_SESSION_RE.search(content):
            continue
        if EXCLUDE_RE.search(content):
            continue
        # Skip short questions (< 20 chars) that are clearly about current topic
        if len(content) < 20 and "session" not in content.lower():
            continue
        candidates.append(t)
    return candidates


def has_search_first_in_assistant_slice(session_file: Path, user_turn: dict) -> bool:
    """Check if the assistant invoked session_search before this user turn.
    Strategy: look for MARKER in the preceding assistant messages within the same session file.
    """
    user_time = None
    marker_found = False

    with open(session_file) as f:
        for line in f:
            try:
                msg = json.loads(line)
            except json.JSONDecodeError:
                continue

            role = msg.get("role", "")
            content = msg.get("content", "") or ""
            tool_calls = msg.get("tool_calls") or []

            # Check content for marker
            if MARKER in content:
                marker_found = True

            # Check tool_calls for session_search
            for tc in tool_calls:
                fn = tc.get("function", {})
                if fn.get("name") == "session_search":
                    marker_found = True

            # When we hit the user turn in question, check what came before
            if role == "user" and content == user_turn["full_content"]:
                # Marker or session_search must be found BEFORE this user message
                return marker_found

    return False


def audit(sample_size: int = 10, days_back: int = 7) -> dict:
    files = collect_sessions(SESSIONS_DIR, days_back)

    if not files:
        return {"ok": False, "error": f"No session files found in {SESSIONS_DIR}"}

    sampled = sample_sessions(files, sample_size)

    total_user_turns = 0
    violations = []
    filtered_violations = []
    all_rows = []

    for sf in sampled:
        turns = user_turns_in_session(sf)
        total_user_turns += len(turns)
        cross_turns = cross_session_user_turns(turns)

        for ct in cross_turns:
            search_ok = has_search_first_in_assistant_slice(sf, ct)
            exclude_reason = None

            if not search_ok:
                exclude_reason = "no session_search before next user turn"

            row = {
                "session_file": ct["session"],
                "user_snippet": ct["content"],
                "search_first_ok": search_ok,
                "evidence": "found preemptive search" if search_ok else "no session_search before next user turn",
                "exclude_reason": exclude_reason,
                "filtered_in_scope": True,
            }
            all_rows.append(row)

            if not search_ok:
                violations.append(row)
                filtered_violations.append(row)
            else:
                violations.append(row)

    total = len(all_rows)
    violation_count = len(violations)
    filtered_violation_count = len(filtered_violations)
    filtered_total = sum(1 for r in all_rows if r["filtered_in_scope"])

    report = {
        "ok": True,
        "sessions_dir": str(SESSIONS_DIR),
        "recall_candidates_total": total_user_turns,
        "sample_size": total,
        "violations": violation_count,
        "violation_rate": round(violation_count / total, 2) if total else 0,
        "filtered_recall_candidates_total": filtered_violation_count,
        "filtered_sample_size": filtered_total,
        "filtered_violations": filtered_violation_count,
        "filtered_violation_rate": round(filtered_violation_count / filtered_total, 2) if filtered_total else 0,
        "rows": all_rows,
        "filtered_rows": [r for r in all_rows if r["filtered_in_scope"]],
    }

    out_path = Path(__file__).parent / "search-first-audit-current.json"
    with open(out_path, "w") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print(f"📊 Audit: {filtered_violation_count}/{filtered_total} filtered violations = {report['filtered_violation_rate']:.0%}")
    print(f"   Raw: {violation_count}/{total} violations = {report['violation_rate']:.0%}")
    print(f"   Session files sampled: {len(sampled)}, total user turns encountered: {total_user_turns}")
    print(f"   Results saved to: {out_path}")
    return report


if __name__ == "__main__":
    sample_size = 10
    days_back = 7
    for arg in sys.argv[1:]:
        if arg.startswith("--sample="):
            sample_size = int(arg.split("=")[1])
        elif arg.startswith("--days="):
            days_back = int(arg.split("=")[1])
    audit(sample_size, days_back)
