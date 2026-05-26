"""Tests for Wave 6 evidence helpers."""

from __future__ import annotations

import time

from mimir_state import SessionDB
from tools.wave6_evidence import compute_feishu_smoke_evidence, compute_search_first_audit


def test_feishu_smoke_and_audit_on_state_db(tmp_path):
    db_path = tmp_path / "state.db"
    db = SessionDB(db_path=db_path)
    sid = "s1"
    db.create_session(sid, source="test")
    db.append_message(sid, role="user", content="上次 IR 论文检索")
    db.append_message(sid, role="tool", content="hits", tool_name="session_search")

    smoke = compute_feishu_smoke_evidence(days=7, db_path=db_path)
    assert smoke["ok"] is True
    assert len(smoke["scenarios"]) == 3

    audit = compute_search_first_audit(days=7, sample_limit=10, db_path=db_path)
    assert audit["ok"] is True
    assert audit["violations"] == 0
