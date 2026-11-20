"""H15-facing checks: canonical tool names aligned with Hermes where decided."""


def test_search_web_not_registered_web_search_is():
    import model_tools  # noqa: F401 — discovery + register_tool_remap("search_web", "web_search")

    from tools.registry import registry

    names = set(registry.get_all_tool_names())
    assert "search_web" not in names
    assert "web_search" in names


def test_route_tool_call_search_web_to_web_search():
    import model_tools  # noqa: F401

    from tools.strategy import route_tool_call

    n, args, err = route_tool_call("search_web", {"query": "parity"})
    assert err is None
    assert n == "web_search"
    assert args == {"query": "parity"}
