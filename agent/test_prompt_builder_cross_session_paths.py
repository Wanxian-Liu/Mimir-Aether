"""Prompt cross-session paths follow MIMIR_AETHER_HOME (not git repo data/)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from agent.prompt_builder import _build_cross_session_context


@pytest.fixture
def clear_home_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in ("MIMIR_AETHER_HOME", "MIMIRAETHER_HOME", "HERMES_HOME"):
        monkeypatch.delenv(key, raising=False)


def test_cross_session_context_reads_runtime_home_persistent(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    clear_home_env: None,
) -> None:
    monkeypatch.setenv("MIMIR_AETHER_HOME", str(tmp_path))
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True)
    (data_dir / "persistent.json").write_text(
        json.dumps(
            {
                "last_session_end": "2026-05-24T12:00:00Z",
                "session_count": 42,
                "curator_nudge": "runtime-home-marker",
            }
        ),
        encoding="utf-8",
    )

    ctx = _build_cross_session_context()
    assert "runtime-home-marker" in ctx
    assert "会话计数: 42" in ctx
    assert "<cross-session-context>" in ctx


def test_cross_session_context_ignores_repo_data_when_home_differs(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    clear_home_env: None,
) -> None:
    repo_root = Path(__file__).resolve().parent.parent
    repo_persistent = repo_root / "data" / "persistent.json"
    if not repo_persistent.is_file():
        pytest.skip("no repo data/persistent.json to contrast")

    monkeypatch.setenv("MIMIR_AETHER_HOME", str(tmp_path))
    (tmp_path / "data").mkdir(parents=True)
    (tmp_path / "data" / "persistent.json").write_text(
        json.dumps({"curator_nudge": "from-mimir-home-only", "session_count": 1}),
        encoding="utf-8",
    )

    ctx = _build_cross_session_context()
    assert "from-mimir-home-only" in ctx
    # Repo file content must not override runtime home (common fork symptom).
    try:
        repo_state = json.loads(repo_persistent.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        pytest.skip("repo persistent.json not valid JSON")
    repo_nudge = repo_state.get("curator_nudge") or ""
    if repo_nudge and repo_nudge != "from-mimir-home-only":
        assert repo_nudge not in ctx


def test_cross_session_next_session_from_home(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    clear_home_env: None,
) -> None:
    monkeypatch.setenv("MIMIR_AETHER_HOME", str(tmp_path))
    (tmp_path / "NEXT_SESSION.md").write_text("NEXT from home\n", encoding="utf-8")

    ctx = _build_cross_session_context()
    assert "NEXT from home" in ctx
