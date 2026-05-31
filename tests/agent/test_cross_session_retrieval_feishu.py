"""OPS-L2-FEISHU-01: Feishu /new path — prefetch consume via gateway session_key."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

import pytest

from agent import cross_session_retrieval as csr
from tools.approval import reset_current_session_key, set_current_session_key


FEISHU_SESSION_KEY = "agent:main:feishu:dm:oc_8af3ea46411e607b3a2e7f2ceed694e8"


@pytest.fixture
def clear_home_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in ("MIMIR_AETHER_HOME", "MIMIRAETHER_HOME", "HERMES_HOME"):
        monkeypatch.delenv(key, raising=False)


def test_feishu_prefetch_via_mimir_session_key_env(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    clear_home_env: None,
) -> None:
    """Gateway executor sets MIMIR_SESSION_KEY; HERMES may be absent or stale."""
    monkeypatch.setenv("MIMIR_AETHER_HOME", str(tmp_path))
    monkeypatch.delenv("HERMES_SESSION_KEY", raising=False)
    monkeypatch.setenv("MIMIR_SESSION_KEY", FEISHU_SESSION_KEY)

    ops = tmp_path / "data" / "ops"
    ops.mkdir(parents=True)
    monkeypatch.setattr(csr, "_prefetch_pending_path", lambda: ops / "session_prefetch_pending.json")

    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "persistent.json").write_text(
        json.dumps({"progress": {"current_objective": "world model horizon"}}),
        encoding="utf-8",
    )

    csr.request_cross_session_prefetch(FEISHU_SESSION_KEY, reason="/new")

    def _fake_search(query: str, **_k: Any) -> List[Dict[str, Any]]:
        return [
            {
                "session_id": "prior-feishu",
                "title": "Feishu prior",
                "source": "feishu",
                "started_at": "2026-05-20",
                "messages": [{"role": "user", "content": "Discussed L2 prefetch"}],
            }
        ]

    out = csr.build_retrieved_sessions_context(search_fn=_fake_search)
    assert "<retrieved-sessions>" in out
    assert "Feishu prior" in out


def test_feishu_prefetch_via_approval_contextvar(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    clear_home_env: None,
) -> None:
    """Executor thread binds session_key before agent init (no HERMES env)."""
    monkeypatch.setenv("MIMIR_AETHER_HOME", str(tmp_path))
    monkeypatch.delenv("HERMES_SESSION_KEY", raising=False)
    monkeypatch.delenv("MIMIR_SESSION_KEY", raising=False)

    ops = tmp_path / "data" / "ops"
    ops.mkdir(parents=True)
    monkeypatch.setattr(csr, "_prefetch_pending_path", lambda: ops / "session_prefetch_pending.json")

    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "persistent.json").write_text(
        json.dumps({"progress": {"current_objective": "OPS-L2 smoke"}}),
        encoding="utf-8",
    )

    csr.request_cross_session_prefetch(FEISHU_SESSION_KEY, reason="/new")
    token = set_current_session_key(FEISHU_SESSION_KEY)
    try:

        def _fake_search(query: str, **_k: Any) -> List[Dict[str, Any]]:
            return [
                {
                    "session_id": "prior-feishu",
                    "title": "Contextvar path",
                    "source": "feishu",
                    "messages": [{"role": "assistant", "content": "ok"}],
                }
            ]

        out = csr.build_retrieved_sessions_context(search_fn=_fake_search)
    finally:
        reset_current_session_key(token)

    assert "<retrieved-sessions>" in out
    assert "Contextvar path" in out
