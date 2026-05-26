"""Tests for session_search 7d usage baseline (IQ-EVO-29)."""

from __future__ import annotations

import json
import time

from mimir_state import SessionDB
from tools.session_search_usage_baseline import compute_session_search_baseline


def _set_started_at(db: SessionDB, sid: str, started_at: float) -> None:
    db._conn.execute(
        "UPDATE sessions SET started_at = ? WHERE id = ?",
        (started_at, sid),
    )
    db._conn.commit()


def _seed_session_with_search(db: SessionDB, *, sid: str, started_at: float) -> None:
    db.create_session(sid, source="test", model="test-model")
    _set_started_at(db, sid, started_at)
    db.append_message(
        sid,
        role="assistant",
        content="searching",
        tool_calls=[{"id": "c1", "type": "function", "function": {"name": "session_search"}}],
    )
    db.append_message(
        sid,
        role="tool",
        content='{"hits": []}',
        tool_name="session_search",
        tool_call_id="c1",
    )


def test_baseline_counts_sessions_with_search(tmp_path):
    db_path = tmp_path / "state.db"
    db = SessionDB(db_path=db_path)
    now = time.time()
    _seed_session_with_search(db, sid="s1", started_at=now - 3600)
    db.create_session("s2", source="test", model="m")
    _set_started_at(db, "s2", now - 7200)
    db.append_message("s2", role="user", content="hi only")

    out = compute_session_search_baseline(days=7, db_path=db_path)
    assert out["ok"] is True
    assert out["total_sessions"] == 2
    assert out["sessions_with_session_search"] == 1
    assert out["session_search_session_rate"] == 0.5
    assert out["session_search_tool_messages"] == 1


def test_mimir_ops_session_search_baseline_action(tmp_path, monkeypatch):
    db_path = tmp_path / "state.db"
    db = SessionDB(db_path=db_path)
    _seed_session_with_search(db, sid="s1", started_at=time.time() - 60)

    monkeypatch.setattr(
        "tools.session_search_usage_baseline.get_mimir_home",
        lambda: tmp_path,
    )
    monkeypatch.setattr(
        "tools.session_search_usage_baseline.compute_session_search_baseline",
        lambda **kw: compute_session_search_baseline(days=7, db_path=db_path),
    )

    from tools import mimir_ops_tool as ops

    payload = json.loads(ops.mimir_ops("session_search_baseline", days=7))
    assert payload["ok"] is True
    assert payload["sessions_with_session_search"] == 1
    assert "output_path" in payload
