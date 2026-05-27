"""HERM-SDH-02: subdirectory hints optional system-prompt tier."""

from __future__ import annotations

from pathlib import Path

import pytest

from agent.prompt_builder import build_system_prompt_parts
from agent.subdirectory_hints import (
    SubdirectoryHintTracker,
    build_subdirectory_hints_system_block,
    subdir_hints_in_system_enabled,
)


def test_subdir_hints_in_system_default_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MIMIR_SUBDIR_HINTS_IN_SYSTEM", raising=False)
    assert not subdir_hints_in_system_enabled()


def test_prompt_block_loads_child_agents_md(tmp_path: Path) -> None:
    backend = tmp_path / "backend"
    backend.mkdir()
    (backend / "AGENTS.md").write_text("backend agents rules", encoding="utf-8")
    block = SubdirectoryHintTracker(working_dir=tmp_path).prompt_block()
    assert block
    assert "backend agents" in block


def test_build_system_prompt_parts_includes_subdir_hints(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("MIMIR_SUBDIR_HINTS_IN_SYSTEM", "1")
    backend = tmp_path / "backend"
    backend.mkdir()
    (backend / "AGENTS.md").write_text("subdir hint for prompt", encoding="utf-8")
    parts = build_system_prompt_parts(
        "deepseek-chat",
        cwd=str(tmp_path),
        include_context=False,
        include_skills=False,
    )
    blob = "\n".join(parts.values())
    assert "subdir hint for prompt" in blob
    assert "<subdirectory-hints>" in blob


def test_build_subdirectory_hints_system_block_respects_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    backend = tmp_path / "svc"
    backend.mkdir()
    (backend / "AGENTS.md").write_text("svc rules", encoding="utf-8")
    monkeypatch.delenv("MIMIR_SUBDIR_HINTS_IN_SYSTEM", raising=False)
    assert build_subdirectory_hints_system_block(cwd=str(tmp_path)) == ""
    monkeypatch.setenv("MIMIR_SUBDIR_HINTS_IN_SYSTEM", "1")
    assert "svc rules" in build_subdirectory_hints_system_block(cwd=str(tmp_path))
