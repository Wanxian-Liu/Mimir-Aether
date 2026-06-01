"""Tests for session_search 7d usage baseline (IQ-EVO-29).

Contains both original-style (inline SessionDB) and harness-style tests.
"""

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


# ---------------------------------------------------------------------------
# Original style (inline SessionDB)
# ---------------------------------------------------------------------------

def test_baseline_counts_sessions_with_search_original(tmp_path):
    """Original: manually create SessionDB with tmp_path."""
    db_path = tmp_path / "state.db"
    db = SessionDB(db_path=db_path)
    now = time.time()
    _seed_session_with_search(db, sid="s1", started_at=now - 3600)
    db.create_session("s2", source="test", model="m")
    _set_started_at(db, "s2", now - 7200)
    db.append_message("s2", role="user", content="hi only")
    db.close()

    out = compute_session_search_baseline(days=7, db_path=db_path)
    assert out["ok"] is True
    assert out["total_sessions"] == 2
    assert out["sessions_with_session_search"] == 1
    assert out["session_search_session_rate"] == 0.5
    assert out["session_search_tool_messages"] == 1


def test_mimir_ops_session_search_baseline_action_original(tmp_path, monkeypatch):
    """Original: manual SessionDB + monkeypatch."""
    db_path = tmp_path / "state.db"
    db = SessionDB(db_path=db_path)
    _seed_session_with_search(db, sid="s1", started_at=time.time() - 60)
    db.close()

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


# ---------------------------------------------------------------------------
# Harness style (using ``harness`` fixture from conftest.py)
# ---------------------------------------------------------------------------

def test_baseline_counts_sessions_with_search(harness):
    """Harness style: harness.db / harness.db_path provided automatically."""
    now = time.time()
    _seed_session_with_search(harness.db, sid="s1", started_at=now - 3600)
    harness.db.create_session("s2", source="test", model="m")
    _set_started_at(harness.db, "s2", now - 7200)
    harness.db.append_message("s2", role="user", content="hi only")

    out = compute_session_search_baseline(days=7, db_path=harness.db_path)
    assert out["ok"] is True
    assert out["total_sessions"] == 2
    assert out["sessions_with_session_search"] == 1
    assert out["session_search_session_rate"] == 0.5
    assert out["session_search_tool_messages"] == 1


def test_harness_faux_llm_provider(harness):
    """Demonstrate FauxLlmProvider usage via harness.faux."""
    faux = harness.faux
    assert faux.call_count == 0

    faux.set_responses([
        {"choices": [{"message": {"content": "first reply"}}]},
        {"choices": [{"message": {"content": "second reply"}}]},
        {"choices": [{"message": {"content": "third reply"}}]},
    ])

    import asyncio

    async def run():
        r1, _lat = await faux.call_model_with_tokens([], "s1")
        assert r1["choices"][0]["message"]["content"] == "first reply"
        r2, _lat = await faux.call_model_with_tokens([], "s1")
        assert r2["choices"][0]["message"]["content"] == "second reply"
        r3, _lat = await faux.call_model_with_tokens([], "s1")
        assert r3["choices"][0]["message"]["content"] == "third reply"
        # Fourth call returns default fallback
        r4, _lat = await faux.call_model_with_tokens([], "s1")
        assert r4["choices"][0]["message"]["content"] == "(default faux reply)"
        assert faux.call_count == 4

    asyncio.run(run())
