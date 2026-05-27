"""OS-TOOL-SRCH-01: ToolRanker — tool + skill search with RRF fusion."""

from __future__ import annotations

from agent.tool_ranker import (
    ToolSearchEntry,
    build_tool_search_index,
    search_tools,
    tool_search_enabled,
)


def _entries() -> list[ToolSearchEntry]:
    return [
        ToolSearchEntry(
            entry_id="tool:read_file",
            kind="tool",
            name="read_file",
            description="Read a file from disk",
            toolset="file",
            text="read_file read a file from disk file",
        ),
        ToolSearchEntry(
            entry_id="tool:web_search",
            kind="tool",
            name="web_search",
            description="Search the web",
            toolset="web",
            text="web_search search the web",
        ),
        ToolSearchEntry(
            entry_id="skill:mimiraether-foo",
            kind="skill",
            name="mimiraether-foo",
            description="Foo skill for testing",
            toolset="",
            category="test",
            text="mimiraether-foo foo skill for testing",
        ),
    ]


def test_tool_search_disabled(monkeypatch) -> None:
    monkeypatch.setenv("MIMIR_TOOL_SEARCH", "0")
    assert not tool_search_enabled()
    assert search_tools("read", entries=_entries()) == []


def test_build_index_merges_tools_and_skills(monkeypatch) -> None:
    monkeypatch.setenv("MIMIR_TOOL_SEARCH", "1")

    monkeypatch.setattr(
        "agent.tool_ranker._iter_registry_tool_entries",
        lambda: [
            ToolSearchEntry(
                entry_id="tool:terminal",
                kind="tool",
                name="terminal",
                description="Run shell",
                toolset="terminal",
                text="terminal run shell execute commands",
            )
        ],
    )
    monkeypatch.setattr(
        "agent.tool_ranker._iter_skill_entries",
        lambda: [
            ToolSearchEntry(
                entry_id="skill:demo-skill",
                kind="skill",
                name="demo-skill",
                description="Demo",
                toolset="",
                category="demo",
                text="demo-skill demo",
            )
        ],
    )
    idx = build_tool_search_index()
    kinds = {e.kind for e in idx}
    names = {e.name for e in idx}
    assert kinds == {"tool", "skill"}
    assert "terminal" in names
    assert "demo-skill" in names


def test_search_tools_lexical_prefers_name_match() -> None:
    hits = search_tools("read file", entries=_entries(), limit=5)
    assert hits
    assert hits[0]["name"] == "read_file"
    assert hits[0]["kind"] == "tool"


def test_search_tools_includes_skills_by_default() -> None:
    hits = search_tools("foo skill", entries=_entries(), limit=5)
    kinds = {h["kind"] for h in hits}
    assert "skill" in kinds


def test_phrase_boost_read_file_over_skills() -> None:
    entries = _entries() + [
        ToolSearchEntry(
            entry_id="skill:write-file-helper",
            kind="skill",
            name="write-file-helper",
            description="Helps with file writes and read workflows",
            toolset="",
            category="test",
            text="write file read workflows",
        ),
    ]
    hits = search_tools("read file", entries=entries, limit=3)
    assert hits[0]["name"] == "read_file"
    assert hits[0]["kind"] == "tool"


def test_build_index_loads_registry_tools() -> None:
    import model_tools  # noqa: F401

    idx = build_tool_search_index(include_skills=False)
    names = {e.name for e in idx if e.kind == "tool"}
    assert "read_file" in names


def test_search_tools_fusion_uses_quality_signal(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("MIMIR_AETHER_HOME", str(tmp_path))
    monkeypatch.setenv("MIMIR_TOOL_QUALITY", "1")
    (tmp_path / "data").mkdir(parents=True)
    from agent.tool_quality import ToolQualityManager

    qm = ToolQualityManager(
        db_path=tmp_path / "data" / "tool_quality.db",
        enable_persistence=True,
    )
    for _ in range(5):
        qm.record("web_search", success=True)
    for _ in range(5):
        qm.record("read_file", success=False, error_message="fail")

    hits = search_tools("search", entries=_entries(), limit=3)
    names = [h["name"] for h in hits]
    assert "web_search" in names
    if len(names) >= 2:
        assert names.index("web_search") < names.index("read_file")
