"""Wave 6 evidence helpers (IQ-EVO-30～34): state.db audits and log scans."""

from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from mimir_constants import get_mimir_home

# Scenario probes for Feishu-style cross-session questions (IQ-EVO-30).
FEISHU_SMOKE_SCENARIOS: Tuple[Tuple[str, str, Tuple[str, ...]], ...] = (
    ("history_ir", "历史 IR / 论文检索", ("ir", "红外", "infrared", "论文", "paper")),
    ("user_preference", "用户偏好", ("偏好", "习惯", "preference", "喜欢")),
    ("last_decision", "上次决策", ("上次", "之前决定", "last time", "decision", "决定")),
)

CROSS_SESSION_KEYWORDS = (
    "上次",
    "之前",
    "历史",
    "记得",
    "说过",
    "last time",
    "previous",
    "earlier",
    "recall",
    "IR",
    "论文",
)


def _session_db_path(db_path: Path | None = None) -> Path:
    return db_path or (get_mimir_home() / "state.db")


def _session_has_session_search(conn: Any, session_id: str) -> bool:
    row = conn.execute(
        """
        SELECT 1 FROM messages m
        WHERE m.session_id = ?
          AND (
            (m.role = 'tool' AND m.tool_name = 'session_search')
            OR (
              m.role = 'assistant'
              AND m.tool_calls IS NOT NULL
              AND m.tool_calls LIKE '%"session_search"%'
            )
          )
        LIMIT 1
        """,
        (session_id,),
    ).fetchone()
    return row is not None


def compute_feishu_smoke_evidence(*, days: int = 7, db_path: Path | None = None) -> Dict[str, Any]:
    """Build 3-scenario table from state.db (documented pass/fail per scenario)."""
    path = _session_db_path(db_path)
    if not path.is_file():
        return {"ok": False, "error": f"state.db not found: {path}", "scenarios": []}

    from mimir_state import SessionDB

    cutoff = time.time() - days * 86400
    db = SessionDB(db_path=path)
    conn = db._conn
    scenarios_out: List[Dict[str, Any]] = []

    for sid, label, keywords in FEISHU_SMOKE_SCENARIOS:
        pattern = "|".join(re.escape(k) for k in keywords)
        rows = conn.execute(
            """
            SELECT s.id, m.content, m.timestamp
            FROM sessions s
            JOIN messages m ON m.session_id = s.id
            WHERE s.started_at >= ?
              AND m.role = 'user'
              AND m.content IS NOT NULL
            """,
            (cutoff,),
        ).fetchall()
        matched_sessions: List[str] = []
        sample_user_line = ""
        for session_id, content, _ts in rows:
            text = content or ""
            if re.search(pattern, text, re.IGNORECASE):
                matched_sessions.append(session_id)
                if not sample_user_line:
                    sample_user_line = text[:120].replace("\n", " ")

        searched = [
            sid for sid in matched_sessions if _session_has_session_search(conn, sid)
        ]
        status = "pass" if searched else ("no_matching_sessions" if not matched_sessions else "fail")
        scenarios_out.append(
            {
                "id": sid,
                "label": label,
                "status": status,
                "matching_sessions": len(matched_sessions),
                "sessions_with_session_search": len(searched),
                "sample_user_snippet": sample_user_line or "(none in window)",
                "evidence": (
                    f"{len(searched)}/{len(matched_sessions)} sessions called session_search"
                    if matched_sessions
                    else f"no user messages matched keywords in last {days}d"
                ),
            }
        )

    return {
        "ok": True,
        "days": days,
        "state_db": str(path),
        "generated_at": time.time(),
        "scenarios": scenarios_out,
    }


def compute_search_first_audit(
    *,
    days: int = 7,
    sample_limit: int = 10,
    db_path: Path | None = None,
) -> Dict[str, Any]:
    """Sample sessions that should search-first; flag missing session_search."""
    path = _session_db_path(db_path)
    if not path.is_file():
        return {"ok": False, "error": f"state.db not found: {path}", "rows": []}

    from mimir_state import SessionDB

    cutoff = time.time() - days * 86400
    db = SessionDB(db_path=path)
    conn = db._conn
    kw_re = re.compile("|".join(re.escape(k) for k in CROSS_SESSION_KEYWORDS), re.IGNORECASE)

    sessions = conn.execute(
        "SELECT id, started_at FROM sessions WHERE started_at >= ? ORDER BY started_at DESC",
        (cutoff,),
    ).fetchall()

    candidates: List[Dict[str, Any]] = []
    for session_id, started_at in sessions:
        user_msgs = conn.execute(
            """
            SELECT content FROM messages
            WHERE session_id = ? AND role = 'user' AND content IS NOT NULL
            ORDER BY timestamp ASC
            """,
            (session_id,),
        ).fetchall()
        hit = any(kw_re.search(m[0] or "") for m in user_msgs)
        if not hit:
            continue
        has_search = _session_has_session_search(conn, session_id)
        snippet = ""
        for (content,) in user_msgs:
            if kw_re.search(content or ""):
                snippet = (content or "")[:100].replace("\n", " ")
                break
        candidates.append(
            {
                "session_id": session_id,
                "started_at": started_at,
                "violation": not has_search,
                "user_snippet": snippet,
            }
        )
        if len(candidates) >= sample_limit:
            break

    violations = sum(1 for c in candidates if c["violation"])
    rate = round(violations / len(candidates), 4) if candidates else None

    return {
        "ok": True,
        "days": days,
        "sample_limit": sample_limit,
        "sampled": len(candidates),
        "violations": violations,
        "violation_rate": rate,
        "rows": candidates,
        "state_db": str(path),
        "generated_at": time.time(),
    }


def _iter_log_files(home: Path, *, days: int) -> List[Path]:
    cutoff = time.time() - days * 86400
    paths: List[Path] = []
    for sub in ("logs", "gateway/logs", "data/logs"):
        base = home / sub
        if not base.is_dir():
            continue
        for p in base.rglob("*.log"):
            try:
                if p.stat().st_mtime >= cutoff:
                    paths.append(p)
            except OSError:
                continue
    return paths


def compute_nudge_counts_7d(*, days: int = 7) -> Dict[str, Any]:
    """Count memory/skill nudge markers in recent log files."""
    home = get_mimir_home()
    memory = 0
    skill = 0
    files_scanned: List[str] = []
    for log_path in _iter_log_files(home, days=days):
        files_scanned.append(str(log_path))
        try:
            text = log_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        memory += text.count("[MIMIR_MEMORY_NUDGE]")
        skill += text.count("[MIMIR_SKILL_NUDGE]")

    return {
        "ok": True,
        "days": days,
        "memory_nudge_count": memory,
        "skill_nudge_count": skill,
        "files_scanned": len(files_scanned),
        "note": "0 counts may mean no logs in window or nudge interval not reached (documented).",
        "generated_at": time.time(),
    }


def compute_jepa_no_candidates_rate(*, days: int = 7) -> Dict[str, Any]:
    """Scan logs for jepa no_candidates vs run_cycle."""
    home = get_mimir_home()
    no_candidates = 0
    run_cycle = 0
    for log_path in _iter_log_files(home, days=days):
        try:
            text = log_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        no_candidates += len(re.findall(r"jepa_cycle skipped reason=no_candidates", text))
        run_cycle += len(re.findall(r"jepa_cycle.*executed|jepa_cycle run", text, re.I))

    total = no_candidates + run_cycle
    rate = round(no_candidates / total, 4) if total else None
    return {
        "ok": True,
        "days": days,
        "no_candidates": no_candidates,
        "run_or_other": run_cycle,
        "no_candidates_rate": rate,
        "trend_note": "compare to Wave 4 baseline in closeout (documented if logs empty)",
        "generated_at": time.time(),
    }


def write_json(data: Dict[str, Any], filename: str) -> Path:
    out_dir = get_mimir_home() / "data" / "ops"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / filename
    out_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return out_path
