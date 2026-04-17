"""
MimirAether Skills Loader

1:1学习Hermes的skill系统，支持：
- SKILL.md解析（YAML frontmatter）
- 按分类组织skill
- skill_view加载完整内容
- skill_manage修改skill

目录结构：
    skills/
    ├── github/
    │   └── github-issues/
    │       └── SKILL.md
    ├── data-science/
    │   └── jupyter-live-kernel/
    │       └── SKILL.md
    └── ...
"""

import json
import logging
import os
import re
import yaml
from pathlib import Path
from typing import Dict, Any, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)

# Skills目录
SKILLS_DIR = Path(__file__).parent
SKILL_FILENAME = "SKILL.md"

# Frontmatter限制（与Hermes一致）
MAX_NAME_LENGTH = 64
MAX_DESCRIPTION_LENGTH = 1024


class SkillLoadError(Exception):
    """Skill加载错误"""
    pass


def _parse_frontmatter(content: str) -> Tuple[Dict[str, Any], str]:
    """
    解析SKILL.md的YAML frontmatter
    
    Returns:
        (frontmatter_dict, markdown_content)
    """
    frontmatter_pattern = re.compile(r'^---\s*\n(.*?)\n---\s*\n(.*)', re.DOTALL)
    match = frontmatter_pattern.match(content)
    
    if match:
        try:
            frontmatter = yaml.safe_load(match.group(1)) or {}
            markdown = match.group(2)
            return frontmatter, markdown
        except yaml.YAMLError as e:
            logger.warning(f"Failed to parse frontmatter: {e}")
            return {}, content
    return {}, content


def _get_skill_dir(name: str) -> Optional[Path]:
    """
    根据skill名称查找skill目录
    
    Args:
        name: skill名称
        
    Returns:
        skill目录Path或None
    """
    # 遍历skills目录查找
    for item in SKILLS_DIR.iterdir():
        if item.is_dir():
            # 直接匹配
            if item.name == name:
                return item
            # 嵌套匹配（如 github/github-issues）
            for subitem in item.iterdir():
                if subitem.is_dir() and subitem.name == name:
                    return subitem
                # 再嵌套一层
                if subitem.is_dir():
                    for subsubitem in subitem.iterdir():
                        if subsubitem.is_dir() and subsubitem.name == name:
                            return subsubitem
    return None


def _read_skill_file(skill_dir: Path, filename: str = SKILL_FILENAME) -> Optional[str]:
    """读取skill文件内容"""
    skill_file = skill_dir / filename
    if skill_file.exists():
        return skill_file.read_text(encoding="utf-8")
    return None


def _load_skill_metadata(skill_dir: Path) -> Optional[Dict[str, Any]]:
    """
    加载skill元数据（从SKILL.md的frontmatter）
    
    Returns:
        {
            "name": str,
            "description": str,
            "version": str,
            "category": str,
            "tags": List[str],
            ...
        }
    """
    content = _read_skill_file(skill_dir)
    if not content:
        return None
    
    frontmatter, _ = _parse_frontmatter(content)
    
    # 提取必要字段
    name = frontmatter.get("name", skill_dir.name)
    description = frontmatter.get("description", "")
    
    # 分类：从目录结构推断
    category = frontmatter.get("category")
    if not category:
        # 从父目录名推断
        parts = skill_dir.parts
        if len(parts) >= 2:
            category = parts[-2]
        else:
            category = "general"
    
    return {
        "name": name,
        "description": description,
        "version": frontmatter.get("version", "1.0.0"),
        "category": category,
        "tags": frontmatter.get("metadata", {}).get("hermes", {}).get("tags", []),
        "dir": str(skill_dir),
    }


def skills_list(category: str = None) -> List[Dict[str, Any]]:
    """
    列出所有可用的skill（只返回元数据，token高效）
    
    Args:
        category: 可选，按分类过滤
        
    Returns:
        skill元数据列表
    """
    results = []
    
    for item in SKILLS_DIR.iterdir():
        if not item.is_dir():
            continue
        
        # 检查子目录
        for skill_dir in item.iterdir():
            if not skill_dir.is_dir():
                continue
            
            # 跳过modules目录
            if skill_dir.name == "modules":
                continue
            
            skill_meta = _load_skill_metadata(skill_dir)
            if not skill_meta:
                continue
            
            # 按分类过滤
            if category and skill_meta.get("category") != category:
                continue
            
            results.append(skill_meta)
    
    # 也检查顶级skill目录
    for item in SKILLS_DIR.iterdir():
        if not item.is_dir():
            continue
        if item.name in ["modules", "__pycache__"]:
            continue
        # 如果item直接包含SKILL.md
        skill_file = item / SKILL_FILENAME
        if skill_file.exists():
            skill_meta = _load_skill_metadata(item)
            if skill_meta:
                if not category or skill_meta.get("category") == category:
                    results.append(skill_meta)
    
    return results


def skill_view(name: str, file_path: str = None) -> Dict[str, Any]:
    """
    加载skill完整内容
    
    Args:
        name: skill名称
        file_path: 可选，加载skill下的具体文件
        
    Returns:
        {
            "name": str,
            "content": str,
            "file_path": str,
        }
    """
    skill_dir = _get_skill_dir(name)
    if not skill_dir:
        raise SkillLoadError(f"Skill not found: {name}")
    
    if file_path:
        # 加载skill下的具体文件
        file_content = _read_skill_file(skill_dir, file_path)
        if not file_content:
            raise SkillLoadError(f"File not found in skill {name}: {file_path}")
        return {
            "name": name,
            "content": file_content,
            "file_path": file_path,
        }
    
    # 加载完整SKILL.md
    content = _read_skill_file(skill_dir)
    if not content:
        raise SkillLoadError(f"SKILL.md not found in skill: {name}")
    
    frontmatter, markdown = _parse_frontmatter(content)
    
    return {
        "name": name,
        "content": markdown.strip(),
        "frontmatter": frontmatter,
        "dir": str(skill_dir),
    }


def get_skills_by_category() -> Dict[str, List[Tuple[str, str]]]:
    """
    按分类获取所有skill（用于构建system prompt）
    
    Returns:
        {
            "github": [("github-issues", "..."), ("github-pr-workflow", "...")],
            "data-science": [("jupyter-live-kernel", "...")],
            ...
        }
    """
    skills_by_category: Dict[str, List[Tuple[str, str]]] = {}
    
    for item in SKILLS_DIR.iterdir():
        if not item.is_dir() or item.name in ["modules", "__pycache__"]:
            continue
        
        # 检查item是否直接是skill（含SKILL.md）
        if (item / SKILL_FILENAME).exists():
            meta = _load_skill_metadata(item)
            if meta:
                cat = meta.get("category", "general")
                skills_by_category.setdefault(cat, []).append(
                    (meta["name"], meta.get("description", ""))
                )
        
        # 检查子目录
        for skill_dir in item.iterdir():
            if not skill_dir.is_dir():
                continue
            if (skill_dir / SKILL_FILENAME).exists():
                meta = _load_skill_metadata(skill_dir)
                if meta:
                    cat = meta.get("category", "general")
                    skills_by_category.setdefault(cat, []).append(
                        (meta["name"], meta.get("description", ""))
                    )
    
    return skills_by_category


def build_skills_prompt() -> str:
    """
    构建skills提示文本（用于system prompt）
    
    Returns:
        <available_skills>...</available_skills>格式的文本
    """
    skills_by_category = get_skills_by_category()
    
    if not skills_by_category:
        return ""
    
    index_lines = []
    for category in sorted(skills_by_category.keys()):
        index_lines.append(f"  {category}:")
        for name, desc in sorted(skills_by_category[category], key=lambda x: x[0]):
            if desc:
                index_lines.append(f"    - {name}: {desc}")
            else:
                index_lines.append(f"    - {name}")
    
    result = (
        "## Skills (mandatory)\n"
        "Before replying, scan the skills below. If a skill matches or is even partially relevant "
        "to your task, you MUST load it with skill_view(name) and follow its instructions. "
        "Err on the side of loading — it is always better to have context you don't need "
        "than to miss critical steps, pitfalls, or established workflows. "
        "Skills contain specialized knowledge — API endpoints, tool-specific commands, "
        "and proven workflows that outperform general-purpose approaches. Load the skill "
        "even if you think you could handle the task with basic tools like web_search or terminal. "
        "Skills also encode the user's preferred approach, conventions, and quality standards "
        "for tasks like code review, planning, and testing — load them even for tasks you "
        "already know how to do, because the skill defines how it should be done here.\n"
        "If a skill has issues, fix it with skill_manage(action='patch').\n"
        "After difficult/iterative tasks, offer to save as a skill. "
        "If a skill you loaded was missing steps, had wrong commands, or needed "
        "pitfalls you discovered, update it before finishing.\n"
        "\n"
        "<available_skills>\n"
        + "\n".join(index_lines) + "\n"
        "</available_skills>\n"
        "\n"
        "Only proceed without loading a skill if genuinely none are relevant to the task."
    )
    
    return result


# 导出
__all__ = [
    "skills_list",
    "skill_view",
    "get_skills_by_category",
    "build_skills_prompt",
    "SkillLoadError",
]
