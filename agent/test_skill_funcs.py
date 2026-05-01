"""Minimal behavior tests for agent/skill_funcs.py (Parity §1)."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent.skill_funcs import (  # noqa: E402
    SKILL_MANAGE_SCHEMA,
    SKILL_TOOL_SCHEMAS,
    skill_manage_func,
    skill_view_func,
    skills_list_func,
)


def test_skill_tool_schemas_have_required_tool_fields():
    for key, schema in SKILL_TOOL_SCHEMAS.items():
        assert schema.get("name") == key
        assert schema.get("description")
        assert schema.get("parameters", {}).get("type") == "object"


def test_skill_manage_schema_action_enum_and_required():
    assert SKILL_MANAGE_SCHEMA.get("name") == "skill_manage"
    params = SKILL_MANAGE_SCHEMA["parameters"]
    assert set(params.get("required", [])) == {"action", "name"}
    action_enum = params["properties"]["action"].get("enum", [])
    assert "create" in action_enum and "delete" in action_enum


def test_skill_view_func_skill_load_error_returns_prefixed_message():
    from skills.skills_loader import SkillLoadError

    with patch("skills.skills_loader.skill_view", side_effect=SkillLoadError("not found")):
        out = skill_view_func("nonexistent-skill-xyz")
    assert out.startswith("Error:")
    assert "not found" in out


def test_skill_view_func_with_file_path_prefixes_filename():
    with patch("skills.skills_loader.skill_view", return_value={"content": "inner"}):
        out = skill_view_func("my-skill", file_path="references/x.md")
    assert "references/x.md" in out
    assert "inner" in out


def test_skill_view_func_without_file_path_returns_content_only():
    with patch("skills.skills_loader.skill_view", return_value={"content": "full skill"}):
        out = skill_view_func("my-skill")
    assert out == "full skill"


def test_skills_list_func_empty_returns_fixed_message():
    with patch("skills.skills_loader.skills_list", return_value=[]):
        assert skills_list_func() == "No skills found."


def test_skills_list_func_formats_names_and_descriptions():
    with patch(
        "skills.skills_loader.skills_list",
        return_value=[
            {"name": "alpha", "description": "first skill"},
            {"name": "beta", "description": ""},
        ],
    ):
        out = skills_list_func()
    assert "Found 2 skills" in out
    assert "alpha" in out and "beta" in out


def test_skill_manage_func_delegates_to_skills_loader():
    with patch("skills.skills_loader.skill_manage", return_value="managed") as m:
        out = skill_manage_func("create", "new-skill", content="# Title", category="test")
    assert out == "managed"
    m.assert_called_once()
    kw = m.call_args.kwargs
    assert kw["action"] == "create"
    assert kw["name"] == "new-skill"
    assert kw["content"] == "# Title"
    assert kw["category"] == "test"
