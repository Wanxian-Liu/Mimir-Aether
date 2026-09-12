"""B1 (2026-09-13): NEXT_SESSION.md excerpts take the **newest dated section**.

Both injection paths used to slice the file *head*, so a stale section could
occupy it indefinitely.  Real incident: 2026-08-21 -> 2026-09-12, an obsolete
"IQ55-60" block sat in the first 400 chars and was injected every turn.

Fix (Liu approved option 2): pick the section whose heading carries the newest
``YYYY-MM-DD``; fall back to the **tail** when no heading is dated.  Zero
migration, no new writing discipline.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from agent.text_sections import latest_dated_section

OLD_MARKER = "IQ55-60 陈旧段"
NEW_MARKER = "上下文归一"

OLD = "# NS 状态（2026-08-21 更新）\n\n## " + OLD_MARKER + "\n" + "x" * 300 + "\n"
NEW = "# NS 状态（2026-09-12 更新）\n\n## 当前目标\n" + NEW_MARKER + "\n"


@pytest.fixture
def clear_home_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in ("MIMIR_AETHER_HOME", "MIMIRAETHER_HOME", "HERMES_HOME"):
        monkeypatch.delenv(key, raising=False)


# --------------------------------------------------------------------------
# helper unit tests
# --------------------------------------------------------------------------


def test_newest_section_wins_when_new_section_is_below() -> None:
    out = latest_dated_section(OLD + NEW, 500)
    assert NEW_MARKER in out
    assert OLD_MARKER not in out


def test_newest_section_wins_when_new_section_is_above() -> None:
    out = latest_dated_section(NEW + OLD, 500)
    assert NEW_MARKER in out
    assert OLD_MARKER not in out


def test_stale_head_never_occupies_the_excerpt() -> None:
    """The 8-21 regression shape: stale block first, fresh block last."""
    out = latest_dated_section(OLD + NEW, 60)
    assert OLD_MARKER not in out
    assert out.startswith("# NS 状态（2026-09-12 更新）")


def test_falls_back_to_tail_when_no_heading_is_dated() -> None:
    out = latest_dated_section("a" * 100 + "TAIL", 10)
    assert out == "aaaaaaTAIL"  # tail, not head


def test_max_len_is_respected() -> None:
    assert len(latest_dated_section(OLD + NEW, 20)) <= 20


def test_non_positive_max_len_returns_empty() -> None:
    assert latest_dated_section(NEW, 0) == ""
    assert latest_dated_section(NEW, -1) == ""


def test_empty_text_returns_empty() -> None:
    assert latest_dated_section("", 50) == ""
    assert latest_dated_section("   \n  ", 50) == ""


def test_dated_subsection_keeps_parent_heading() -> None:
    text = "# 父（2026-01-01）\n\n## 子（2026-09-13）\n内容是新的\n"
    out = latest_dated_section(text, 500)
    assert out.startswith("# 父（2026-01-01）")  # context kept
    assert "内容是新的" in out


def test_same_date_prefers_shallower_heading() -> None:
    text = "# Top（2026-09-10）\ntop body\n\n## Sub（2026-09-10）\nsub body\n"
    out = latest_dated_section(text, 500)
    assert out.startswith("# Top（2026-09-10）")


def test_heading_without_date_is_not_a_boundary_error() -> None:
    """A dated section followed by an undated heading still resolves."""
    text = "# A（2026-01-01）\nold\n\n# 备注\nno date here\n"
    out = latest_dated_section(text, 500)
    assert out.startswith("# A（2026-01-01）")


# --------------------------------------------------------------------------
# integration: the two real call sites
# --------------------------------------------------------------------------


def test_prompt_builder_injection_uses_newest_section(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    clear_home_env: None,
) -> None:
    from agent.prompt_builder import _build_cross_session_context

    monkeypatch.setenv("MIMIR_AETHER_HOME", str(tmp_path))
    (tmp_path / "NEXT_SESSION.md").write_text(OLD + NEW, encoding="utf-8")

    ctx = _build_cross_session_context()
    assert NEW_MARKER in ctx
    assert OLD_MARKER not in ctx


def test_prompt_builder_injection_falls_back_to_tail(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    clear_home_env: None,
) -> None:
    from agent.prompt_builder import _build_cross_session_context

    monkeypatch.setenv("MIMIR_AETHER_HOME", str(tmp_path))
    (tmp_path / "NEXT_SESSION.md").write_text("flat undated note\n", encoding="utf-8")

    ctx = _build_cross_session_context()
    assert "flat undated note" in ctx


def test_cross_session_snippet_uses_newest_section(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    clear_home_env: None,
) -> None:
    from agent.cross_session_retrieval import _next_session_snippet

    monkeypatch.setenv("MIMIR_AETHER_HOME", str(tmp_path))
    (tmp_path / "NEXT_SESSION.md").write_text(OLD + NEW, encoding="utf-8")

    snippet = _next_session_snippet()
    assert NEW_MARKER in snippet
    assert OLD_MARKER not in snippet


def test_cross_session_snippet_keeps_legacy_flat_file_working(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    clear_home_env: None,
) -> None:
    """Backwards-compat: undated single-line files behave as before."""
    from agent.cross_session_retrieval import _next_session_snippet

    monkeypatch.setenv("MIMIR_AETHER_HOME", str(tmp_path))
    (tmp_path / "NEXT_SESSION.md").write_text(
        "Continue horizon C master iteration", encoding="utf-8"
    )

    assert "horizon C" in _next_session_snippet()
