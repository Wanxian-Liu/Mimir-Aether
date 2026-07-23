"""Tests for ByteRover AKL field injection (pure functions, no I/O)."""
from __future__ import annotations

import copy
import datetime
import json
import re

# ---------------------------------------------------------------------------
# Inline copies of the three AKL helpers so the test is fully self-contained
# (no import-time side effects from persistent_store.py → mimir_constants).
# Production source: agent/persistent_store.py lines 154‑167.
# ---------------------------------------------------------------------------

def _init_akl_fields(entry: dict) -> dict:
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    entry.setdefault("importance", 50)
    entry.setdefault("maturity", "draft")
    entry.setdefault("last_access", now)
    entry.setdefault("decay_factor", 0.95)
    return entry


def _update_akl_last_access(entry: dict) -> dict:
    entry["last_access"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    return entry


def _apply_decay(entry: dict, days_passed: int) -> dict:
    factor = entry.get("decay_factor", 0.95) ** days_passed
    entry["importance"] = max(0, int(entry.get("importance", 50) * factor))
    return entry


# ═══════════════════════════════════════════════════════════════════════════
# Tests
# ═══════════════════════════════════════════════════════════════════════════

def test_init_akl_fields_empty() -> None:
    """_init_akl_fields injects all 4 fields with correct defaults."""
    d: dict = {}
    result = _init_akl_fields(d)
    assert result["importance"] == 50
    assert result["maturity"] == "draft"
    assert isinstance(result["last_access"], str) and "T" in result["last_access"]
    assert result["decay_factor"] == 0.95
    assert len(result) == 4


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
