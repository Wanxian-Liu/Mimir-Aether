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

