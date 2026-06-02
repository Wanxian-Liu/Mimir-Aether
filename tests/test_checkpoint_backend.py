"""Tests for CheckpointManager — save, load, clear, expiry, corruption."""

import json
import os
import sys
import time
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from checkpoint_manager import CheckpointManager, CheckpointState


# ── Fixtures ──────────────────────────────────────────────────────────────


@pytest.fixture
def mgr():
    """CheckpointManager with a temporary directory, cleaned up after."""
    with tempfile.TemporaryDirectory() as tmp:
        yield CheckpointManager(checkpoint_dir=Path(tmp))


def _fake_state(**overrides) -> dict:
    state = {
        "conversation_history": [{"role": "user", "content": "hello"}],
        "iteration_used": 3,
        "session_id": "sess-001",
        "user_message": "hello",
    }
    state.update(overrides)
    return state


# ── Tests ─────────────────────────────────────────────────────────────────


class TestCheckpointSaveLoad:
    """save_checkpoint → load_checkpoint → data integrity."""

    def test_save_then_load_returns_matching_data(self, mgr):
        task_id = "test-save-load"
        state = _fake_state()
        assert mgr.save_checkpoint(task_id, state, current_step=5, next_action="continue")
        loaded = mgr.load_checkpoint(task_id)
        assert loaded is not None
        assert loaded.task_id == task_id
        assert loaded.current_step == 5
        assert loaded.iteration_used == 3
        assert len(loaded.conversation_history) == 1
        assert loaded.next_action == "continue"

    def test_load_nonexistent_returns_none(self, mgr):
        assert mgr.load_checkpoint("never-saved") is None


class TestCheckpointClear:
    """clear_checkpoint removes data; subsequent load returns None."""

    def test_clear_removes_checkpoint(self, mgr):
        task_id = "test-clear"
        mgr.save_checkpoint(task_id, _fake_state())
        assert mgr.load_checkpoint(task_id) is not None
        assert mgr.clear_checkpoint(task_id)
        assert mgr.load_checkpoint(task_id) is None

    def test_clear_nonexistent_returns_true(self, mgr):
        assert mgr.clear_checkpoint("does-not-exist")


class TestCheckpointExpiry:
    """Expired checkpoints are auto-cleaned on load."""

    def test_expired_checkpoint_returns_none(self, mgr):
        task_id = "test-expired"
        mgr.save_checkpoint(task_id, _fake_state())
        # Manually backdate the file
        path = mgr._get_checkpoint_path(task_id)
        assert path.exists()
        data = json.loads(path.read_text(encoding="utf-8"))
        data["updated_at"] = time.time() - (mgr._max_age_hours + 1) * 3600
        path.write_text(json.dumps(data), encoding="utf-8")
        # Now load should return None and delete the file
        assert mgr.load_checkpoint(task_id) is None
        assert not path.exists()


class TestCheckpointCorruption:
    """Corrupted or malformed JSON returns None gracefully."""

    def test_corrupted_json_returns_none(self, mgr):
        task_id = "test-corrupted"
        path = mgr._get_checkpoint_path(task_id)
        path.write_text("{invalid json", encoding="utf-8")
        assert mgr.load_checkpoint(task_id) is None

    def test_empty_file_returns_none(self, mgr):
        task_id = "test-empty"
        path = mgr._get_checkpoint_path(task_id)
        path.write_text("", encoding="utf-8")
        assert mgr.load_checkpoint(task_id) is None

    def test_missing_optional_fields_use_defaults(self, mgr):
        """Optional fields missing from JSON fall back to .get() defaults."""
        task_id = "test-defaults"
        path = mgr._get_checkpoint_path(task_id)
        # Include updated_at to avoid expiry; omit other optional fields
        path.write_text(json.dumps({
            "task_id": task_id,
            "updated_at": time.time(),
        }), encoding="utf-8")
        loaded = mgr.load_checkpoint(task_id)
        assert loaded is not None
        assert loaded.conversation_history == []
        assert loaded.current_step == 0


class TestTaskIdSafety:
    """_generate_task_id produces stable, safe IDs."""

    def test_same_message_same_id(self, mgr):
        msg = "帮我写一个程序"
        assert mgr._generate_task_id(msg) == mgr._generate_task_id(msg)

    def test_different_message_different_id(self, mgr):
        assert mgr._generate_task_id("msg A") != mgr._generate_task_id("msg B")

    def test_special_chars_sanitized(self, mgr):
        safe = mgr._get_checkpoint_path("../../etc/passwd")
        assert ".." not in safe.name
        assert safe.name.startswith("checkpoint_")
