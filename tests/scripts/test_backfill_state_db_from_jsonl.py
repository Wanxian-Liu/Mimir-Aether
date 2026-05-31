"""IQ-IDX-01: backfill_state_db_from_jsonl idempotency."""

from __future__ import annotations

import json
from pathlib import Path


def test_backfill_creates_session_and_messages(tmp_path, monkeypatch):
    home = tmp_path / "home"
    sessions = home / "data" / "sessions"
    sessions.mkdir(parents=True)
    sid = "20260101_120000_test01"
    (sessions / f"{sid}.jsonl").write_text(
        "\n".join(
            [
                json.dumps({"role": "session_meta", "platform": "test", "timestamp": "2026-01-01T12:00:00Z"}),
                json.dumps({"role": "user", "content": "hello", "tool_name": "session_search"}),
                json.dumps({"role": "assistant", "content": "world"}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("MIMIR_AETHER_HOME", str(home))
    monkeypatch.setenv("MIMIRAETHER_HOME", str(home))

    from scripts.backfill_state_db_from_jsonl import run_backfill

    r1 = run_backfill(sessions_dir=sessions, db_path=home / "state.db", limit=None, dry_run=False)
    assert r1["ok"] is True
    assert r1["sessions_created"] >= 1
    assert r1["messages_appended"] >= 2

    r2 = run_backfill(sessions_dir=sessions, db_path=home / "state.db", limit=None, dry_run=False)
    assert r2["messages_skipped"] >= r1["messages_appended"]
