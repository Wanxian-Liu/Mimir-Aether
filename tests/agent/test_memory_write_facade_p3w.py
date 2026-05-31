"""ENGINE-P3W-01 · MemoryWriteFacade routing."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from agent import memory_write_facade as mwf


def test_write_capsule_html_creates_file(tmp_path, monkeypatch):
    cap_dir = tmp_path / "memory" / "capsules"
    monkeypatch.setattr(mwf, "get_capsules_dir", lambda: cap_dir)
    path = cap_dir / "test-capsule.html"
    mwf.write_capsule_html(filepath=path, html="<html><body>ok</body></html>")
    assert path.read_text(encoding="utf-8").startswith("<html>")


def test_write_persistent_mutator_skill_usage(tmp_path, monkeypatch):
    data_file = tmp_path / "persistent.json"
    data_file.write_text(
        json.dumps({"version": "1.4", "memory": {}, "progress": {}}),
        encoding="utf-8",
    )
    monkeypatch.setattr(mwf.persistent_store, "get_persistent_path", lambda: data_file)

    mwf.write_persistent_mutator(lambda d: d.__setitem__("skill_usage", {"s1": "2026-05-28"}))

    loaded = json.loads(data_file.read_text(encoding="utf-8"))
    assert loaded["skill_usage"] == {"s1": "2026-05-28"}
