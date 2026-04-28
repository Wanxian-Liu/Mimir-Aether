"""
# MimirAether Skill Functions
# 独立技能查看/列表/管理函数

从 core_loop.py 提取的技能相关函数。
这些是模块级函数，供 Agent 调用。
"""

from typing import Optional


def skill_view_func(name: str, file_path: str = None) -> str:
    """
    加载skill完整内容

    Args:
        name: skill名称
        file_path: 可选,加载skill下的具体文件

    Returns:
        skill内容
    """
    from skills.skills_loader import skill_view as _skill_view, SkillLoadError
    try:
        result = _skill_view(name, file_path)
        if file_path:
            return f"文件: {file_path}\n\n{result['content']}"
        return result['content']
    except SkillLoadError as e:
        return f"Error: {e}"


def skills_list_func(category: str = None) -> str:
    """
    列出所有可用的skill

    Args:
        category: 可选,按分类过滤

    Returns:
        skill列表
    """
    from skills.skills_loader import skills_list as _skills_list
    skills = _skills_list(category)
    if not skills:
        return "No skills found."

    lines = [f"Found {len(skills)} skills:\n"]
    for s in skills:
        lines.append(f"- {s['name']}: {s.get('description', 'No description')[:60]}")
    return "\n".join(lines)


# Skill工具schema
SKILL_TOOL_SCHEMAS = {
    "skill_view": {
        "name": "skill_view",
        "description": "Load the full content of a skill by name. Use this to get the complete instructions for a skill.",
        "parameters": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "The name of the skill to view"
                },
                "file_path": {
                    "type": "string",
                    "description": "Optional: Load a specific file within the skill (e.g., 'references/api.md')"
                }
            },
            "required": ["name"]
        }
    },
    "skills_list": {
        "name": "skills_list",
        "description": "List all available skills. Returns skill names and descriptions.",
        "parameters": {
            "type": "object",
            "properties": {
                "category": {
                    "type": "string",
                    "description": "Optional: Filter by category (e.g., 'github', 'data-science')"
                }
            }
        }
    }
}


def skill_manage_func(
    action: str,
    name: str,
    content: str = None,
    category: str = None,
    file_path: str = None,
    file_content: str = None,
    old_string: str = None,
    new_string: str = None,
    replace_all: bool = False,
) -> str:
    """
    管理skill(创建、编辑、删除)

    Actions:
    - create: 创建新skill
    - edit: 编辑skill(完整重写)
    - patch: 打补丁(局部修改)
    - delete: 删除skill
    - write_file: 写入skill下的文件
    - remove_file: 删除skill下的文件
    """
    from skills.skills_loader import skill_manage as _skill_manage
    return _skill_manage(
        action=action,
        name=name,
        content=content,
        category=category,
        file_path=file_path,
        file_content=file_content,
        old_string=old_string,
        new_string=new_string,
        replace_all=replace_all,
    )


# Skill管理工具schema
SKILL_MANAGE_SCHEMA = {
    "name": "skill_manage",
    "description": (
        "Manage skills (create, update, delete). Skills are your procedural memory - "
        "reusable approaches for recurring task types.\n\n"
        "Actions: create (full SKILL.md + optional category), "
        "patch (old_string/new_string - preferred for fixes), "
        "edit (full SKILL.md rewrite), "
        "delete, write_file, remove_file.\n\n"
        "Create when: complex task succeeded (5+ calls), errors overcome, "
        "user-corrected approach worked, non-trivial workflow discovered.\n"
        "Update when: instructions stale/wrong, missing steps or pitfalls found.\n"
        "After difficult tasks, offer to save as a skill."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["create", "patch", "edit", "delete", "write_file", "remove_file"],
                "description": "The action to perform"
            },
            "name": {"type": "string", "description": "Skill name"},
            "content": {"type": "string", "description": "Full SKILL.md content for create/edit"},
            "category": {"type": "string", "description": "Category for new skill"},
            "file_path": {"type": "string", "description": "File path within skill"},
            "file_content": {"type": "string", "description": "File content for write_file"},
            "old_string": {"type": "string", "description": "Text to find for patch"},
            "new_string": {"type": "string", "description": "Replacement text for patch"},
            "replace_all": {"type": "boolean", "description": "Replace all occurrences"},
        },
        "required": ["action", "name"]
    }
}


# 导出
__all__ = [
    "skill_view_func",
    "skills_list_func",
    "skill_manage_func",
    "SKILL_TOOL_SCHEMAS",
    "SKILL_MANAGE_SCHEMA",
]
