"""Memory tool must receive a MemoryStore via dispatch (not fail with store=None)."""

import json
import os

import pytest


@pytest.fixture
def isolated_memory_home(tmp_path, monkeypatch):
    """Use a temp Mimir home so MEMORY.md / USER.md writes stay isolated."""
    home = str(tmp_path / "mimir_home")
    monkeypatch.setenv("MIMIR_AETHER_HOME", home)
    monkeypatch.setenv("MIMIRAETHER_HOME", home)
    from tools.memory_tool import reset_memory_store_for_test

    reset_memory_store_for_test()
    yield home
    reset_memory_store_for_test()


def test_memory_dispatch_add_persists(isolated_memory_home):
    import model_tools  # noqa: F401 — registers tools via _discover_tools

    from tools.registry import registry

    raw = registry.dispatch(
        "memory",
        {
            "action": "add",
            "target": "memory",
            "content": "User prefers concise replies.",
        },
    )
    data = json.loads(raw)
    assert data.get("success") is True
    assert "User prefers concise replies." in data.get("entries", [])

    mem_file = os.path.join(isolated_memory_home, "memories", "MEMORY.md")
    assert os.path.isfile(mem_file)
    assert "User prefers concise replies." in open(mem_file, encoding="utf-8").read()


def test_handle_function_call_memory_add(isolated_memory_home):
    import model_tools
    from model_tools import handle_function_call

    raw = handle_function_call(
        "memory",
        {
            "action": "add",
            "target": "user",
            "content": "Name: Ray",
        },
    )
    data = json.loads(raw)
    assert data.get("success") is True
    user_file = os.path.join(isolated_memory_home, "memories", "USER.md")
    assert os.path.isfile(user_file)
