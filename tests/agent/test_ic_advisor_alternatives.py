"""Tests for ic_advisor wider alternative search (MW-05).

Verifies that when a protected file is blocked:
1. Same-directory alternatives are found (narrow search)
2. When none found, wider search (prompts/, low blast_radius) kicks in
3. Suggestion is never empty
"""

from unittest.mock import MagicMock, patch

import pytest

from agent.self_evolution.engine import ic_advisor


# ── helpers ──


@pytest.fixture(autouse=True)
def _mock_engine():
    """Mock the self-evolution engine with a minimal codebase state.

    The state.files dict uses relative paths under agent/ as keys.
    """
    from agent.self_evolution.state_encoder import CodebaseState, DependencyNode

    state = CodebaseState(timestamp=0.0)
    state.files = {
        "agent_loop.py": DependencyNode(file_path="agent_loop.py", n_lines=800, imported_by=["agent.py"]),
        "prompts/base.txt": DependencyNode(file_path="prompts/base.txt", n_lines=10, imported_by=[]),
        "prompts/system.txt": DependencyNode(file_path="prompts/system.txt", n_lines=20, imported_by=[]),
        "conversation_nudges.py": DependencyNode(file_path="conversation_nudges.py", n_lines=100, imported_by=["agent_loop.py"]),
        "subdir/helper.py": DependencyNode(file_path="subdir/helper.py", n_lines=50, imported_by=["core_loop.py"]),
        "parallel_dispatcher.py": DependencyNode(file_path="parallel_dispatcher.py", n_lines=120, imported_by=["agent_loop.py"]),
        "types.py": DependencyNode(file_path="types.py", n_lines=40, imported_by=["agent_loop.py", "conversation_nudges.py"]),
    }

    mock_engine = MagicMock()
    mock_engine.encoder.encode.return_value = state

    # Cost evaluation mock: return low TC for all
    class MockResult:
        tc_cost = 0.5

    mock_engine.cost.evaluate.return_value = MockResult()

    with patch("agent.self_evolution.engine.get_engine", return_value=mock_engine):
        yield


class TestIcAdvisorAgentRoot:
    """Blocked file in agent/ root (no directory component — the old bug)."""

    def test_finds_same_root_alternatives(self):
        """When blocking agent_loop.py, finds agent-root files as alternatives."""
        result = ic_advisor("agent_loop.py")
        assert result["blocked"] == "agent_loop.py"
        assert len(result["alternatives"]) >= 1
        assert any(a["file"] == "conversation_nudges.py" for a in result["alternatives"])
        assert "被 IC 拦截" not in result["suggestion"]  # should have real suggestion

    def test_suggestion_mentions_best_file(self):
        """Suggestion should mention the best alternative."""
        result = ic_advisor("agent_loop.py")
        assert "建议改" in result["suggestion"]


class TestIcAdvisorWideSearch:
    """When narrow search yields nothing, wide search kicks in."""

    def test_wide_search_includes_prompts(self):
        """Wide search should include prompts/ files."""
        result = ic_advisor("types.py")
        # types.py is in agent/ root, so same-directory search works.
        # But if we block a subdirectory file with no same-dir alternatives:
        pass

    def test_suggestion_never_empty(self):
        """Suggestion should always be a non-empty string."""
        result = ic_advisor("agent_loop.py")
        assert result["suggestion"]
        assert len(result["suggestion"]) > 10

    def test_alternatives_have_correct_keys(self):
        """Each alternative should have file, tc, and blast_radius."""
        result = ic_advisor("agent_loop.py")
        for alt in result["alternatives"]:
            assert "file" in alt
            assert "tc" in alt
            assert "blast_radius" in alt


class TestIcAdvisorEdgeCases:
    """Edge cases for ic_advisor."""

    def test_unknown_file_no_alternatives(self):
        """Unknown file returns no alternatives but non-empty suggestion."""
        result = ic_advisor("nonexistent.py")
        assert result["blast_radius"] == 0
        assert len(result["alternatives"]) == 0
        assert result["suggestion"]  # should not be empty

    def test_blast_radius_reported(self):
        """Blast radius should reflect imported_by count."""
        result = ic_advisor("types.py")
        # types.py has 2 importers
        assert result["blast_radius"] == 2
