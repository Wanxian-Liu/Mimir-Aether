"""IQ-MEM-01: discover_knowledge fallback when ML components are unavailable."""

from __future__ import annotations

import json
import os

import pytest


@pytest.fixture
def isolated_memory_home(tmp_path, monkeypatch):
    home = str(tmp_path / "mimir_home")
    monkeypatch.setenv("MIMIR_AETHER_HOME", home)
    monkeypatch.setenv("MIMIRAETHER_HOME", home)
    from tools.memory_tool import reset_memory_store_for_test

    reset_memory_store_for_test()
    yield home
    reset_memory_store_for_test()


def test_discover_fallback_no_ml_components(monkeypatch, isolated_memory_home):
    import tools.memory_tool as mt

    monkeypatch.setattr(mt, "KnowledgeExtractor", None)
    monkeypatch.setattr(mt, "KnowledgeDeduplicator", None)
    monkeypatch.setattr(mt, "ImportanceScorer", None)

    import model_tools  # noqa: F401

    from tools.registry import registry

    registry.dispatch(
        "memory",
        {
            "action": "add",
            "target": "memory",
            "content": "Gateway single instance uses ensure_single_gateway.sh script.",
        },
    )

    raw = registry.dispatch(
        "memory",
        {
            "action": "discover",
            "texts": ["gateway 双实例 ensure_single_gateway"],
            "current_task": "gateway single instance OPS",
        },
    )
    data = json.loads(raw)
    assert data.get("success") is True
    assert data.get("mode") == "fallback_keyword"
    assert "Knowledge discovery components not available" not in (data.get("error") or "")
    assert isinstance(data.get("candidates"), list)


def test_discover_fallback_empty_store(monkeypatch):
    import tools.memory_tool as mt

    monkeypatch.setattr(mt, "KnowledgeExtractor", None)
    monkeypatch.setattr(mt, "KnowledgeDeduplicator", None)
    monkeypatch.setattr(mt, "ImportanceScorer", None)

    result = mt.discover_knowledge(
        ["unrelated topic xyz"],
        store=None,
        current_task="unrelated topic xyz",
    )
    assert result["success"] is True
    assert result["mode"] == "fallback_keyword"
    assert result["candidates"] == []
