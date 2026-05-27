"""P3-XSR-03: L3 cross-session RAG prefetch flag."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import patch

import pytest

from agent import cross_session_retrieval as csr


@pytest.fixture
def clear_home_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in ("MIMIR_AETHER_HOME", "MIMIRAETHER_HOME", "HERMES_HOME"):
        monkeypatch.delenv(key, raising=False)


def test_rag_default_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MIMIR_CROSS_SESSION_RAG", raising=False)
    assert csr.cross_session_rag_enabled() is False


def test_rag_enabled_by_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MIMIR_CROSS_SESSION_RAG", "1")
    assert csr.cross_session_rag_enabled() is True


def test_run_prefetch_search_rag_off_uses_session_search_path() -> None:
    calls: Dict[str, Any] = {}

    def _prefetch(query: str, **kwargs: Any) -> List[Dict[str, Any]]:
        calls["query"] = query
        calls["kwargs"] = kwargs
        return []

    csr.run_prefetch_search("hello", use_rag=False, prefetch_fn=_prefetch)
    assert calls["kwargs"]["use_rag"] is False


def test_run_prefetch_search_rag_on_passes_flag() -> None:
    calls: Dict[str, Any] = {}

    def _prefetch(query: str, **kwargs: Any) -> List[Dict[str, Any]]:
        calls["kwargs"] = kwargs
        return [{"session_id": "s1", "title": "T", "messages": []}]

    csr.run_prefetch_search("hello", use_rag=True, prefetch_fn=_prefetch)
    assert calls["kwargs"]["use_rag"] is True


def test_build_with_rag_off_matches_l2_search_fn(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    clear_home_env: None,
) -> None:
    monkeypatch.setenv("MIMIR_AETHER_HOME", str(tmp_path))
    monkeypatch.setenv("HERMES_SESSION_KEY", "sk-rag")
    monkeypatch.delenv("MIMIR_CROSS_SESSION_RAG", raising=False)
    ops = tmp_path / "data" / "ops"
    ops.mkdir(parents=True)
    monkeypatch.setattr(csr, "_prefetch_pending_path", lambda: ops / "session_prefetch_pending.json")
    (tmp_path / "data").mkdir(parents=True, exist_ok=True)
    (tmp_path / "data" / "persistent.json").write_text(
        json.dumps({"progress": {"current_objective": "objective"}}),
        encoding="utf-8",
    )

    fusion_called = {"n": 0}

    def _prefetch(query: str, **kwargs: Any) -> List[Dict[str, Any]]:
        if kwargs.get("use_rag"):
            fusion_called["n"] += 1
        return [
            {
                "session_id": "s1",
                "title": "Lexical only",
                "source": "cli",
                "started_at": "2026-05-01",
                "messages": [{"role": "user", "content": "hit"}],
            }
        ]

    csr.request_cross_session_prefetch("sk-rag")
    out = csr.build_retrieved_sessions_context(prefetch_fn=_prefetch)
    assert fusion_called["n"] == 0
    assert "Lexical only" in out


def test_build_with_rag_on_merged_injection(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    clear_home_env: None,
) -> None:
    monkeypatch.setenv("MIMIR_AETHER_HOME", str(tmp_path))
    monkeypatch.setenv("HERMES_SESSION_KEY", "sk-rag2")
    monkeypatch.setenv("MIMIR_CROSS_SESSION_RAG", "1")
    ops = tmp_path / "data" / "ops"
    ops.mkdir(parents=True)
    monkeypatch.setattr(csr, "_prefetch_pending_path", lambda: ops / "session_prefetch_pending.json")
    (tmp_path / "data").mkdir(parents=True, exist_ok=True)
    (tmp_path / "data" / "persistent.json").write_text(
        json.dumps({"progress": {"current_objective": "semantic topic"}}),
        encoding="utf-8",
    )

    def _prefetch(query: str, **kwargs: Any) -> List[Dict[str, Any]]:
        assert kwargs.get("use_rag") is True
        return [
            {
                "session_id": "s-semantic",
                "title": "Fused session",
                "source": "feishu",
                "started_at": "2026-05-02",
                "messages": [{"role": "assistant", "content": "RRF merged hit"}],
            }
        ]

    csr.request_cross_session_prefetch("sk-rag2")
    out = csr.build_retrieved_sessions_context(prefetch_fn=_prefetch)
    assert "<retrieved-sessions>" in out
    assert "Fused session" in out
    assert "RRF merged hit" in out


def test_session_search_prefetch_fusion_when_rag_on(monkeypatch: pytest.MonkeyPatch) -> None:
    from tools.session_search_tool import session_search_prefetch

    fused = [
        {
            "session_id": "f1",
            "title": "Fusion",
            "source": "cli",
            "started_at": "x",
            "messages": [{"role": "user", "content": "a"}],
        }
    ]

    with patch(
        "tools.session_search_tool._semantic_index_ready",
        return_value=True,
    ), patch(
        "tools.session_search_tool._session_search_via_fusion",
        return_value=fused,
    ) as fusion_mock, patch(
        "tools.session_search_tool.session_search",
    ) as plain_mock:
        out = session_search_prefetch("q", use_rag=True)
        fusion_mock.assert_called_once()
        plain_mock.assert_not_called()
        assert out[0]["title"] == "Fusion"


def test_session_search_prefetch_rag_off_uses_session_search(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from tools.session_search_tool import session_search_prefetch

    with patch(
        "tools.session_search_tool._session_search_via_fusion",
    ) as fusion_mock, patch(
        "tools.session_search_tool.session_search",
        return_value=[],
    ) as plain_mock:
        session_search_prefetch("q", use_rag=False)
        fusion_mock.assert_not_called()
        plain_mock.assert_called_once()
