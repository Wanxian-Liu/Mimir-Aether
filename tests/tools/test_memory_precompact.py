"""Pre-compaction snapshot guard for MemoryStore._maybe_compact.

Loss class guarded (2026-09-13): compaction truncated long entries with
" [...] (truncated)" and dropped others, leaving no full-text copy on disk
(the .bak is itself overwritten by later saves). These tests pin the guard:
a <MEMORY.md>.precompact snapshot of the untruncated text is written before
any mutation, only when compaction triggers, and its failure never breaks
compaction.
"""

from __future__ import annotations

import logging

import pytest

SNAP_SUFFIX = ".precompact"
LONG = "L" * 200 + "." + "M" * 380  # 581 chars -> a truncation target


@pytest.fixture
def iso(tmp_path, monkeypatch):
    home = str(tmp_path / "mimir_home")
    monkeypatch.setenv("MIMIR_AETHER_HOME", home)
    monkeypatch.setenv("MIMIRAETHER_HOME", home)
    import tools.memory_tool as mt

    mt.reset_memory_store_for_test()
    # Deterministic: optional ML components live outside the repo.
    monkeypatch.setattr(mt, "KnowledgeDeduplicator", None)
    monkeypatch.setattr(mt, "ImportanceScorer", None)
    store = mt.MemoryStore(memory_char_limit=1000)
    yield mt, store
    mt.reset_memory_store_for_test()


def _snap_path(mt, target="memory"):
    p = mt.MemoryStore._path_for(target)
    return p.with_name(p.name + SNAP_SUFFIX)


def _fill(store):
    # 581 + 400 + 200 + 2 delimiters = 987 chars > 80% of the 1000 limit
    store.memory_entries = [LONG, "x" * 400, "y" * 200]


def test_snapshot_holds_untruncated_text_when_compaction_runs(iso, caplog):
    mt, store = iso
    _fill(store)

    with caplog.at_level(logging.INFO, logger="tools.memory_tool"):
        report = store._maybe_compact("memory")

    assert report["compacted"] is True
    snap = _snap_path(mt)
    assert snap.exists(), "pre-compaction snapshot missing"
    text = snap.read_text(encoding="utf-8")
    assert LONG in text, "snapshot must hold the FULL entry"
    assert "truncated" not in text, "snapshot must be pre-truncation"

    # Post-compaction on-disk state IS lossy -> snapshot is the only full copy
    disk = mt.MemoryStore._path_for("memory").read_text(encoding="utf-8")
    assert LONG not in disk
    assert "(truncated)" in disk

    msgs = [r.getMessage() for r in caplog.records]
    hits = [m for m in msgs if "[MEMORY-PRECOMPACT]" in m]
    assert hits, "missing [MEMORY-PRECOMPACT] log line"
    assert "target=memory" in hits[0]
    assert "entries=3" in hits[0]
    assert str(snap) in hits[0]


def test_no_snapshot_below_threshold(iso):
    mt, store = iso
    store.memory_entries = ["small one", "small two"]

    assert store._maybe_compact("memory") == {}
    assert not _snap_path(mt).exists(), "must not snapshot when no compaction"


def test_snapshot_failure_does_not_break_compaction(iso, monkeypatch, caplog):
    mt, store = iso
    _fill(store)
    original_chars = store._char_count("memory")

    def boom(path, content):
        raise OSError("disk full (simulated)")

    monkeypatch.setattr(mt.MemoryStore, "_snapshot_write", staticmethod(boom))

    with caplog.at_level(logging.WARNING, logger="tools.memory_tool"):
        report = store._maybe_compact("memory")

    # Compaction still completed normally (same behaviour as without snapshot)
    assert report["compacted"] is True
    assert report["original_chars"] == original_chars
    assert report["new_count"] == 3
    assert report["new_chars"] < original_chars
    assert not _snap_path(mt).exists()

    disk = mt.MemoryStore._path_for("memory").read_text(encoding="utf-8")
    assert disk == mt.ENTRY_DELIMITER.join(store.memory_entries)
    assert "(truncated)" in disk

    warn = [r.getMessage() for r in caplog.records if "[MEMORY-PRECOMPACT]" in r.getMessage()]
    assert warn, "snapshot failure must be reported"
