"""IQ-EVO-49 grain B: key_decisions + learned_patterns in cross-session prompt."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from agent.prompt_builder import _build_cross_session_context


@pytest.fixture
def clear_home_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in ("MIMIR_AETHER_HOME", "MIMIRAETHER_HOME", "HERMES_HOME"):
        monkeypatch.delenv(key, raising=False)


def test_cross_session_includes_key_decisions_and_patterns(
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
                "session_count": 3,
                "memory": {
                    "key_decisions": [
                        {"decision": "decision-0", "context": ""},
                        {"decision": "decision-1", "context": ""},
                        {"decision": "decision-2", "context": ""},
                        {"decision": "decision-3", "context": ""},
                        {"decision": "decision-4", "context": ""},
                        {"decision": "ship grain B", "context": "iq-evo-49"},
                    ],
                    "learned_patterns": [
                        {"pattern": "flush before /new", "evidence": "grain A"},
                    ],
                },
            }
        ),
        encoding="utf-8",
    )

    ctx = _build_cross_session_context()
    assert "关键决策" in ctx
    assert "ship grain B" in ctx
    assert "decision-0" not in ctx
    assert "decision-1" in ctx
    assert "学到模式" in ctx
    assert "flush before /new" in ctx


def test_cross_session_legacy_string_decisions(
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
                "session_count": 1,
                "memory": {
                    "key_decisions": ["plain-string decision"],
                    "learned_patterns": ["plain-string pattern"],
                },
            }
        ),
        encoding="utf-8",
    )

    ctx = _build_cross_session_context()
    assert "plain-string decision" in ctx
    assert "plain-string pattern" in ctx


def test_cross_session_empty_memory_no_error(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    clear_home_env: None,
) -> None:
    monkeypatch.setenv("MIMIR_AETHER_HOME", str(tmp_path))
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True)
    (data_dir / "persistent.json").write_text(
        json.dumps({"session_count": 0, "memory": {}}),
        encoding="utf-8",
    )

    ctx = _build_cross_session_context()
    assert "会话计数: 0" in ctx
    assert "关键决策" not in ctx
