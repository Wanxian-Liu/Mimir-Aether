"""P3-XSR-02: L2 cross-session retrieval prefetch."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

import pytest

from agent import cross_session_retrieval as csr


@pytest.fixture
def clear_home_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in ("MIMIR_AETHER_HOME", "MIMIRAETHER_HOME", "HERMES_HOME"):
        monkeypatch.delenv(key, raising=False)


def test_retrieval_disabled_by_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MIMIR_CROSS_SESSION_RETRIEVAL", "0")
    monkeypatch.setenv("HERMES_SESSION_KEY", "feishu:1")
    csr.request_cross_session_prefetch("feishu:1")
    assert csr.build_retrieved_sessions_context() == ""


def test_skips_without_prefetch_pending(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    clear_home_env: None,
) -> None:
    monkeypatch.setenv("MIMIR_AETHER_HOME", str(tmp_path))
    monkeypatch.setenv("HERMES_SESSION_KEY", "feishu:1")
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "persistent.json").write_text(
        json.dumps({"progress": {"current_objective": "world model paper"}}),
        encoding="utf-8",
    )

    called = {"n": 0}

    def _fake_search(*_a: Any, **_k: Any) -> List[Dict[str, Any]]:
        called["n"] += 1
        return []

    out = csr.build_retrieved_sessions_context(search_fn=_fake_search)
    assert out == ""
    assert called["n"] == 0


def test_prefetch_uses_objective_query(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    clear_home_env: None,
) -> None:
    monkeypatch.setenv("MIMIR_AETHER_HOME", str(tmp_path))
    monkeypatch.setenv("HERMES_SESSION_KEY", "feishu:chat1")
    ops = tmp_path / "data" / "ops"
    ops.mkdir(parents=True)
    monkeypatch.setattr(csr, "_prefetch_pending_path", lambda: ops / "session_prefetch_pending.json")

    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "persistent.json").write_text(
        json.dumps({"progress": {"current_objective": "ADR-002 write path"}}),
        encoding="utf-8",
    )

    csr.request_cross_session_prefetch("feishu:chat1", reason="/new")
    captured: Dict[str, Any] = {}

    def _fake_search(query: str, **kwargs: Any) -> List[Dict[str, Any]]:
        captured["query"] = query
        captured["kwargs"] = kwargs
        return [
            {
                "session_id": "sess-abc",
                "title": "Prior chat",
                "source": "feishu",
                "started_at": "2026-05-20",
                "messages": [
                    {"role": "user", "content": "Discussed world model"},
                    {"role": "assistant", "content": "Summary of paper"},
                ],
            }
        ]

    out = csr.build_retrieved_sessions_context(search_fn=_fake_search)
    assert captured["query"] == "ADR-002 write path"
    assert "<retrieved-sessions>" in out
    assert "Prior chat" in out
    assert "Discussed world model" in out
    assert csr.build_retrieved_sessions_context(search_fn=_fake_search) == ""


def test_query_falls_back_to_next_session(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    clear_home_env: None,
) -> None:
    monkeypatch.setenv("MIMIR_AETHER_HOME", str(tmp_path))
    monkeypatch.setenv("HERMES_SESSION_KEY", "sk1")
    ops = tmp_path / "data" / "ops"
    ops.mkdir(parents=True)
    monkeypatch.setattr(csr, "_prefetch_pending_path", lambda: ops / "session_prefetch_pending.json")

    (tmp_path / "data").mkdir(parents=True, exist_ok=True)
    (tmp_path / "data" / "persistent.json").write_text("{}", encoding="utf-8")
    (tmp_path / "NEXT_SESSION.md").write_text(
        "Continue horizon C master iteration",
        encoding="utf-8",
    )

    csr.request_cross_session_prefetch("sk1")
    captured: Dict[str, str] = {}

    def _fake_search(query: str, **_k: Any) -> List[Dict[str, Any]]:
        captured["query"] = query
        return []

    csr.build_retrieved_sessions_context(search_fn=_fake_search)
    assert "horizon C" in captured["query"]


def test_format_respects_max_chars() -> None:
    results = [
        {
            "session_id": "x" * 80,
            "title": "T" * 200,
            "source": "cli",
            "started_at": "2026-05-01",
            "messages": [{"role": "user", "content": "y" * 2000}],
        }
    ]
    out = csr.format_retrieved_sessions(results, max_chars=350)
    assert len(out) <= 350
    assert out.endswith("</retrieved-sessions>")
