"""Tests for ByteRover AKL field injection (pure functions, no I/O).

S1' (2026-10-13 · 会议卡 §B): the three AKL helpers are **imported from the
production module** (``agent.persistent_store``) instead of being inlined here —
the decay formula / metadata schema must not live only in the test file
(B2/F7 读数: production-side ``_apply_decay`` hits = 0 before this change).

``pythonpath = .`` (pytest.ini) makes ``agent.*`` importable from the repo root.
"""
from __future__ import annotations

import copy
import datetime
import json
import re

from agent.persistent_store import (
    _apply_decay,
    _init_akl_fields,
    _apply_lifecycle_decay,
    _update_akl_last_access,
)


# ═══════════════════════════════════════════════════════════════════════════
# Tests
# ═══════════════════════════════════════════════════════════════════════════

def test_init_akl_fields_empty() -> None:
    """_init_akl_fields injects all 6 fields with correct defaults."""
    d: dict = {}
    result = _init_akl_fields(d)
    assert result["importance"] == 50
    assert result["maturity"] == "draft"
    assert isinstance(result["last_access"], str) and "T" in result["last_access"]
    assert result["decay_factor"] == 0.95
    assert isinstance(result["created_at"], str) and "T" in result["created_at"]
    assert result["access_count"] == 0
    assert len(result) == 6


def test_init_akl_fields_does_not_overwrite() -> None:
    """setdefault must NOT overwrite an existing value."""
    d: dict = {"importance": 99, "maturity": "core"}
    result = _init_akl_fields(d)
    assert result["importance"] == 99
    assert result["maturity"] == "core"


def test_update_last_access_changes_timestamp() -> None:
    """_update_akl_last_access replaces the timestamp."""
    old_ts = "2020-01-01T00:00:00"
    d: dict = {"last_access": old_ts}
    _update_akl_last_access(d)
    assert d["last_access"] != old_ts
    assert isinstance(d["last_access"], str) and "T" in d["last_access"]


def test_update_last_access_increments_access_count() -> None:
    """S1' metadata: every touch bumps access_count (missing => counts as 0)."""
    d: dict = {"last_access": "2020-01-01T00:00:00"}
    _update_akl_last_access(d)
    assert d["access_count"] == 1
    _update_akl_last_access(d)
    assert d["access_count"] == 2


def test_apply_decay_reduces_importance() -> None:
    """After 10 days, importance should be strictly lower."""
    d: dict = {"importance": 100, "decay_factor": 0.95}
    _apply_decay(d, 10)
    assert d["importance"] < 100
    assert d["importance"] > 0  # 100 * 0.95¹⁰ ≈ 60


def test_apply_decay_floor_zero() -> None:
    """importance can never go below 0."""
    d: dict = {"importance": 5, "decay_factor": 0.1}
    _apply_decay(d, 365)
    assert d["importance"] == 0


def test_apply_decay_default_factor() -> None:
    """When decay_factor is missing, fallback to 0.95."""
    d: dict = {"importance": 100}
    _apply_decay(d, 30)
    # 100 * 0.95³⁰ ≈ 21
    assert d["importance"] == 21


# ── _apply_lifecycle_decay (S1' ③: entry-level 整并 on the write path) ──────


def _iso(days_ago: int) -> str:
    return (
        datetime.datetime.now(datetime.timezone.utc)
        - datetime.timedelta(days=days_ago)
    ).isoformat()


def test_lifecycle_decay_lowers_aged_and_spares_fresh() -> None:
    """Aged entries lose score; freshly-touched entries keep theirs."""
    data = {
        "memory": {
            "key_decisions": [
                {"decision": "old", "importance": 50, "last_access": _iso(30)},
                {"decision": "fresh", "importance": 50, "last_access": _iso(0)},
            ],
            "learned_patterns": [
                {"pattern": "old", "importance": 80, "last_access": _iso(10)},
            ],
        }
    }
    changed = _apply_lifecycle_decay(data)
    kd = data["memory"]["key_decisions"]
    lp = data["memory"]["learned_patterns"]
    assert changed == 2
    assert kd[0]["importance"] < 50          # aged => decayed
    assert kd[1]["importance"] == 50         # fresh => untouched
    assert lp[0]["importance"] < 80


def test_lifecycle_decay_never_deletes_and_is_idempotent() -> None:
    """Zero-loss: same row count, and a second pass the same day is a no-op."""
    data = {
        "memory": {
            "key_decisions": [{"decision": "d", "importance": 90, "last_access": _iso(5)}],
            "learned_patterns": [{"pattern": "p", "importance": 50, "last_access": _iso(5)}],
        }
    }
    before_rows = len(data["memory"]["key_decisions"]) + len(data["memory"]["learned_patterns"])
    _apply_lifecycle_decay(data)
    once = data["memory"]["key_decisions"][0]["importance"]
    changed2 = _apply_lifecycle_decay(data)
    after_rows = len(data["memory"]["key_decisions"]) + len(data["memory"]["learned_patterns"])
    assert after_rows == before_rows          # never deletes
    assert changed2 == 0                      # idempotent within the same day
    assert data["memory"]["key_decisions"][0]["importance"] == once


def test_lifecycle_decay_tolerates_missing_or_bad_last_access() -> None:
    """No last_access / unparseable => skip, never crash, never invent a score."""
    data = {
        "memory": {
            "key_decisions": [
                {"decision": "no-ts", "importance": 50},
                {"decision": "bad-ts", "importance": 50, "last_access": "not-a-date"},
                "not-a-dict",
            ],
        }
    }
    changed = _apply_lifecycle_decay(data)
    assert changed == 0
    assert data["memory"]["key_decisions"][0]["importance"] == 50
    assert data["memory"]["key_decisions"][1]["importance"] == 50
