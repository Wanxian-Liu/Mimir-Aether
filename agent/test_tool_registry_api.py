"""Parity-facing tests for `agent.tool_registry.ToolRegistry` (enable/disable, search, stats)."""

import threading

from agent.tool_registry import ToolRegistry


def test_tool_registry_enable_disable_list_all(tmp_path):
    db_path = str(tmp_path / "tools.db")
    reg = ToolRegistry(db_path=db_path)

    reg.register(name="t1", category="test", description="d1")
    reg.register(name="t2", category="test", description="d2")

    # Default: enabled_only=True should show both.
    all_enabled = reg.list_all(enabled_only=True)
    assert {t["name"] for t in all_enabled} == {"t1", "t2"}

    reg.disable("t2")
    all_enabled2 = reg.list_all(enabled_only=True)
    assert {t["name"] for t in all_enabled2} == {"t1"}

    all_including_disabled = reg.list_all(enabled_only=False)
    assert {t["name"] for t in all_including_disabled} == {"t1", "t2"}


def test_tool_registry_search_order_and_get_stats(tmp_path):
    db_path = str(tmp_path / "tools.db")
    reg = ToolRegistry(db_path=db_path)

    reg.register(name="alpha_tool", category="test", description="desc")
    reg.register(name="beta_tool", category="test", description="desc")

    hits = reg.search("alpha")
    assert hits and hits[0]["name"] == "alpha_tool"

    reg.log_call("alpha_tool", success=True, duration_ms=12.5)
    reg.log_call("alpha_tool", success=False, duration_ms=2.0, error="x")

    stats = reg.get_stats("alpha_tool", days=7)
    assert "alpha_tool" in stats
    s = stats["alpha_tool"]
    assert s["total_calls"] == 2
    assert s["successful_calls"] == 1
    assert abs(s["success_rate"] - 0.5) < 1e-9


def test_tool_registry_get_none_when_disabled(tmp_path):
    db_path = str(tmp_path / "tools.db")
    reg = ToolRegistry(db_path=db_path)
    reg.register(name="off_tool", category="test", description="d")
    assert reg.get("off_tool") is not None
    reg.disable("off_tool")
    assert reg.get("off_tool") is None


def test_tool_registry_search_ignores_disabled(tmp_path):
    db_path = str(tmp_path / "tools.db")
    reg = ToolRegistry(db_path=db_path)
    reg.register(name="visible_kw", category="test", description="keyword token")
    reg.register(name="hidden_kw", category="test", description="keyword token")
    reg.disable("hidden_kw")
    hits = reg.search("keyword")
    assert {t["name"] for t in hits} == {"visible_kw"}


def test_tool_registry_enable_restores_get_and_search(tmp_path):
    db_path = str(tmp_path / "tools.db")
    reg = ToolRegistry(db_path=db_path)
    reg.register(name="toggle_me", category="test", description="unique-find-xyz")
    reg.disable("toggle_me")
    assert reg.get("toggle_me") is None
    assert not any(t["name"] == "toggle_me" for t in reg.search("unique-find"))

    assert reg.enable("toggle_me") is True
    assert reg.get("toggle_me") is not None
    assert any(t["name"] == "toggle_me" for t in reg.search("unique-find"))


def test_tool_registry_unregister_removes_from_db(tmp_path):
    db_path = str(tmp_path / "tools.db")
    reg = ToolRegistry(db_path=db_path)
    reg.register(name="gone", category="test", description="d")
    assert reg.unregister("gone") is True
    assert reg.get("gone") is None
    assert reg.list_all(enabled_only=False) == []


def test_tool_registry_register_updates_duplicate_name(tmp_path):
    """ENG-WF-12: IntegrityError path updates existing row."""
    db_path = str(tmp_path / "tools.db")
    reg = ToolRegistry(db_path=db_path)
    assert reg.register(name="dup", category="a", description="v1") is True
    assert reg.register(name="dup", category="b", description="v2") is True
    row = reg.get("dup")
    assert row is not None
    assert row["category"] == "b"
    assert row["description"] == "v2"


def test_tool_registry_list_categories_and_filter(tmp_path):
    db_path = str(tmp_path / "tools.db")
    reg = ToolRegistry(db_path=db_path)
    reg.register(name="f1", category="cat_a", description="d")
    reg.register(name="f2", category="cat_b", description="d")
    assert set(reg.list_categories()) == {"cat_a", "cat_b"}
    only_a = reg.list_all(category="cat_a")
    assert len(only_a) == 1 and only_a[0]["name"] == "f1"


def test_tool_registry_enable_missing_returns_false(tmp_path):
    db_path = str(tmp_path / "tools.db")
    reg = ToolRegistry(db_path=db_path)
    assert reg.enable("no_such_tool") is False
    reg.register(name="x", category="t", description="d")
    reg.close()
    reg2 = ToolRegistry(db_path=db_path)
    assert reg2.get("x") is not None

