"""IND-05 / ADR-001: persistent.json single-writer (threading lock + runtime home)."""

from __future__ import annotations

import json
import threading
from pathlib import Path

import pytest

from agent import persistent_store


def _minimal_persistent() -> dict:
    return {
        "version": "1.0",
        "memory": {
            "key_decisions": [],
            "learned_patterns": [],
            "active_projects": [],
            "user_preferences": {},
            "skills_used": [],
        },
        "progress": {
            "current_objective": None,
            "completed_milestones": [],
            "pending_tasks": [],
        },
        "session_count": 0,
    }


@pytest.fixture
def runtime_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("MIMIR_AETHER_HOME", str(tmp_path))
    (tmp_path / "data").mkdir(parents=True)
    persistent_store.save(_minimal_persistent())
    return tmp_path


def test_persistent_path_uses_mimir_data_dir(runtime_home: Path) -> None:
    assert persistent_store.get_persistent_path() == runtime_home / "data" / "persistent.json"


def test_save_rejects_missing_required_keys(runtime_home: Path) -> None:
    with pytest.raises(ValueError, match="missing critical keys"):
        persistent_store.save({"version": "1.0"})


def test_concurrent_segment_updates_both_persist(runtime_home: Path) -> None:
    """Two writers must not lose each other's segments (GH #20 / Session 72 class)."""
    barrier = threading.Barrier(2)
    errors: list[BaseException] = []

    def touch_skill_usage() -> None:
        try:
            barrier.wait(timeout=5)
            persistent_store.read_modify_write(
                lambda data: data.setdefault("skill_usage", {}).update({"skill-a": "t1"})
            )
        except BaseException as e:
            errors.append(e)

    def touch_pending_tasks() -> None:
        try:
            barrier.wait(timeout=5)
            persistent_store.read_modify_write(
                lambda data: data.setdefault("progress", {}).setdefault(
                    "pending_tasks", []
                ).append("from-thread-2")
            )
        except BaseException as e:
            errors.append(e)

    t1 = threading.Thread(target=touch_skill_usage)
    t2 = threading.Thread(target=touch_pending_tasks)
    t1.start()
    t2.start()
    t1.join(timeout=10)
    t2.join(timeout=10)

    assert not errors, errors
    final = json.loads(persistent_store.get_persistent_path().read_text(encoding="utf-8"))
    assert final.get("skill_usage", {}).get("skill-a") == "t1"
    assert "from-thread-2" in final.get("progress", {}).get("pending_tasks", [])


def test_cross_session_save_preserves_concurrent_skill_usage(runtime_home: Path) -> None:
    from agent.cross_session_memory import CrossSessionMemory

    persistent_store.read_modify_write(
        lambda data: data.setdefault("skill_usage", {}).update({"kept": "yes"})
    )
    mem = CrossSessionMemory()
    mem.load()
    mem.set_progress(current_objective="IND-05 test objective")
    assert mem.save() is True

    final = json.loads(persistent_store.get_persistent_path().read_text(encoding="utf-8"))
    assert final.get("skill_usage", {}).get("kept") == "yes"
    assert final.get("progress", {}).get("current_objective") == "IND-05 test objective"
