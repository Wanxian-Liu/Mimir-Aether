"""Gate A3: search_first_audit script smoke."""

from __future__ import annotations

import json
from pathlib import Path

from scripts.search_first_audit import run_audit


def test_run_audit_returns_rows(tmp_path, monkeypatch):
    sessions = tmp_path / "sessions"
    sessions.mkdir()
    path = sessions / "s1.jsonl"
    path.write_text(
        "\n".join(
            [
                '{"role":"user","content":"查历史 IR-20260520"}',
                '{"role":"assistant","content":"找到了 3 个 session 命中 session_search"}',
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "scripts.search_first_audit.get_mimir_home",
        lambda: tmp_path,
    )
    out = run_audit(sessions_dir=sessions, limit=10)
    assert out["ok"] is True
    assert out["sample_size"] >= 1
