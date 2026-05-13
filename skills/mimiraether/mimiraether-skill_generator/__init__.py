"""
MimirAether Skill Generator
============================

检测系统技能缺口，生成完整SKILL.md并注册到技能目录。

核心功能:
- detect_gap(): 检测系统缺失的能力
- generate_skill_md(name, description, code): 生成完整SKILL.md
- register_skill(skill_name): 注册技能到目录
- verify_skill(skill_name): 验证技能可用性

使用三环闭环架构（Monitor→Decision→Execution）进行技能缺口检测和生成。
"""

import os
import re
import glob
import yaml
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple
from pathlib import Path

from mimir_constants import get_mimir_home

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 路径常量（随 MIMIR_AETHER_HOME）
_MIMIR_HOME = get_mimir_home()
SKILLS_DIR = _MIMIR_HOME / "skills" / "mimiraether"
MIMICORE_DIR = _MIMIR_HOME / "mimicore"

# 必需的核心能力列表
CORE_CAPABILITIES = [
    "skill_generator",      # 技能生成
    "auto_testing",         # 自动测试
    "self_evolution",       # 自我进化
    "checkpoint",          # 检查点
    "context_compressor",  # 上下文压缩
    "context_engine",      # 上下文引擎
    "cross_session",        # 跨会话
    "memory_nudge",        # 记忆推送
    "hermes_integration",  # Hermes集成
    "performance_monitor", # 性能监控
    "plan_mode",           # 规划模式
    "root_cause_debugging", # 根因调试
    "smart_routing",       # 智能路由
    "tdd",                 # 测试驱动
    "three_ring_iteration", # 三环迭代
    "tools_system",        # 工具系统
]


def _get_existing_skills() -> List[str]:
    """获取已存在的技能列表"""
    existing = []
    if SKILLS_DIR.exists():
        for skill_dir in SKILLS_DIR.iterdir():
            if skill_dir.is_dir() and skill_dir.name.startswith("mimiraether-"):
                skill_name = skill_dir.name.replace("mimiraether-", "")
                existing.append(skill_name)
    return existing


def _parse_skill_md(skill_path: Path) -> Optional[Dict[str, Any]]:
    """解析SKILL.md的frontmatter"""
    try:
        with open(skill_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 提取frontmatter
        if content.startswith('---'):
            parts = content.split('---', 2)
            if len(parts) >= 3:
                frontmatter = yaml.safe_load(parts[1])
                return frontmatter
    except Exception as e:
        logger.warning(f"Failed to parse {skill_path}: {e}")
    return None


def _is_skeleton_skill(skill_path: Path) -> bool:
    """检查是否是骨架技能（待实现）"""
    try:
        with open(skill_path, 'r', encoding='utf-8') as f:
            content = f.read()
        return "实现状态" in content and "骨架技能" in content
    except:
        return False


def _is_valid_skill(skill_path: Path) -> bool:
    """检查技能是否有效（非骨架）"""
    return not _is_skeleton_skill(skill_path)


# ========== 核心功能 ==========

def detect_gap() -> Dict[str, Any]:
    """
    检测系统中缺失的能力。
    
    基于三环闭环架构的监控环，定期扫描技能目录，
    识别缺失的核心能力和骨架技能。
    
    返回格式:
    {
        "gaps": [
            {"name": "xxx", "reason": "缺失原因", "severity": 0.8},
            ...
        ],
        "existing_skills": [...],
        "missing_capabilities": [...]
    }
    """
    logger.info("[SkillGenerator] Starting gap detection...")
    
    # 获取现有技能
    existing_skills = _get_existing_skills()
    logger.info(f"[SkillGenerator] Found {len(existing_skills)} existing skills")
    
    # 检测缺失的核心能力
    missing_capabilities = []
    for capability in CORE_CAPABILITIES:
        if capability not in existing_skills:
            missing_capabilities.append({
                "name": capability,
                "reason": f"核心能力 '{capability}' 未实现",
                "severity": 0.9 if capability in ["skill_generator", "auto_testing", "self_evolution"] else 0.7
            })
            logger.info(f"[SkillGenerator] Gap detected: {capability}")
    
    # 检测骨架技能（需要实现的）
    skeleton_skills = []
    if SKILLS_DIR.exists():
        for skill_dir in SKILLS_DIR.iterdir():
            if skill_dir.is_dir():
                skill_md = skill_dir / "SKILL.md"
                if skill_md.exists() and _is_skeleton_skill(skill_md):
                    skill_name = skill_dir.name.replace("mimiraether-", "")
                    skeleton_skills.append({
                        "name": skill_name,
                        "reason": "骨架技能需要完整实现",
                        "severity": 0.6
                    })
                    logger.info(f"[SkillGenerator] Skeleton skill found: {skill_name}")
    
    # 合并缺口
    all_gaps = missing_capabilities + skeleton_skills
    
    result = {
        "timestamp": datetime.now().isoformat(),
        "gaps": all_gaps,
        "existing_skills": existing_skills,
        "missing_capabilities": [g["name"] for g in missing_capabilities],
        "skeleton_skills": [s["name"] for s in skeleton_skills],
        "total_gaps": len(all_gaps)
    }
    
    logger.info(f"[SkillGenerator] Gap detection complete: {len(all_gaps)} gaps found")
    return result


def generate_skill_md(
    name: str,
    description: str,
    code: Optional[str] = None,
    version: str = "1.0",
    author: str = "MimirAether"
) -> str:
    """
    生成完整的SKILL.md内容。
    
    Args:
        name: 技能名称 (kebab-case)
        description: 技能描述
        code: 核心实现代码（可选）
        version: 版本号
        author: 作者
    
    Returns:
        完整的SKILL.md内容字符串
    """
    logger.info(f"[SkillGenerator] Generating SKILL.md for: {name}")
    
    # 清理名称
    name = name.lower().strip().replace(" ", "-")
    if not name.startswith("mimiraether-"):
        name = f"mimiraether-{name}"
    
    # 构建frontmatter
    frontmatter = {
        "name": name,
        "description": description,
        "version": version,
        "created": datetime.now().strftime("%Y-%m-%d"),
        "author": author
    }
    
    # 生成SKILL.md内容
    content_parts = [
        "---",
        yaml.dump(frontmatter, allow_unicode=True, default_flow_style=False).strip(),
        "---",
        "",
        f"# {name.replace('mimiraether-', '').replace('-', ' ').title()}",
        "",
        f"> {description}",
        "",
        "## 概述",
        "",
        description,
        "",
        "## 核心功能",
        "",
    ]
    
    # 如果提供了代码，生成功能描述
    if code:
        # 尝试从代码中提取函数定义
        functions = re.findall(r'def (\w+)\s*\(', code)
        if functions:
            for func in functions:
                content_parts.append(f"### {func}()")
                content_parts.append("")
                content_parts.append(f"- 功能: 待实现")
                content_parts.append("")
        else:
            content_parts.append("- 核心功能待定义")
            content_parts.append("")
    
    # 添加标准章节
    standard_sections = [
        "## 使用方式",
        "",
        "```python",
        f"# 导入技能",
        f"from mimiraether_{name.replace('mimiraether-', '')} import ...",
        "",
        "# 使用示例",
        "result = skill_function()",
        "```",
        "",
        "## 依赖",
        "",
        "- MimirAether核心模块",
        "- 三环闭环架构",
        "",
        "## 验证",
        "",
        "```bash",
        f"python3 -c 'from mimiraether_{name.replace('mimiraether-', '')} import ...'",
        "```",
        "",
        "---",
        f"*Generated by MimirAether Skill Generator @ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*"
    ]
    
    content_parts.extend(standard_sections)
    
    result = "\n".join(content_parts)
    logger.info(f"[SkillGenerator] SKILL.md generated for {name}")
    return result


def register_skill(skill_name: str) -> Dict[str, Any]:
    """
    将技能注册到技能目录。
    
    Args:
        skill_name: 技能名称
    
    Returns:
        注册结果 {"success": bool, "path": str, "message": str}
    """
    logger.info(f"[SkillGenerator] Registering skill: {skill_name}")
    
    # 清理名称
    skill_name = skill_name.lower().strip().replace(" ", "-")
    if not skill_name.startswith("mimiraether-"):
        skill_name = f"mimiraether-{skill_name}"
    
    # 创建技能目录
    skill_dir = SKILLS_DIR / skill_name
    skill_md_path = skill_dir / "SKILL.md"
    
    try:
        # 检查是否已存在
        if skill_dir.exists():
            logger.warning(f"[SkillGenerator] Skill directory already exists: {skill_dir}")
            return {
                "success": False,
                "path": str(skill_dir),
                "message": f"技能目录已存在: {skill_name}"
            }
        
        # 创建目录
        skill_dir.mkdir(parents=True, exist_ok=True)
        
        # 生成默认SKILL.md
        skill_md_content = generate_skill_md(
            name=skill_name,
            description=f"自动创建的技能: {skill_name}",
            version="1.0"
        )
        
        # 写入文件
        with open(skill_md_path, 'w', encoding='utf-8') as f:
            f.write(skill_md_content)
        
        logger.info(f"[SkillGenerator] Skill registered successfully: {skill_dir}")
        return {
            "success": True,
            "path": str(skill_dir),
            "skill_md": str(skill_md_path),
            "message": f"技能注册成功: {skill_name}"
        }
        
    except Exception as e:
        logger.error(f"[SkillGenerator] Failed to register skill: {e}")
        return {
            "success": False,
            "path": str(skill_dir),
            "message": f"注册失败: {str(e)}"
        }


def verify_skill(skill_name: str) -> Dict[str, Any]:
    """
    验证技能是否可用。
    
    验证项:
    - SKILL.md存在且格式正确
    - frontmatter有效
    - 核心函数可导入（如果有__init__.py）
    
    Args:
        skill_name: 技能名称
    
    Returns:
        验证结果 {
            "valid": True/False,
            "checks": {...},
            "issues": [...]
        }
    """
    logger.info(f"[SkillGenerator] Verifying skill: {skill_name}")
    
    # 清理名称
    skill_name = skill_name.lower().strip().replace(" ", "-")
    if not skill_name.startswith("mimiraether-"):
        skill_name = f"mimiraether-{skill_name}"
    
    skill_dir = SKILLS_DIR / skill_name
    skill_md_path = skill_dir / "SKILL.md"
    
    checks = {
        "directory_exists": skill_dir.exists(),
        "file_exists": skill_md_path.exists(),
        "frontmatter_valid": False,
        "importable": False
    }
    
    issues = []
    
    # 检查1: 目录存在
    if not checks["directory_exists"]:
        issues.append(f"技能目录不存在: {skill_dir}")
    
    # 检查2: SKILL.md存在
    if not checks["file_exists"]:
        issues.append(f"SKILL.md不存在: {skill_md_path}")
    
    # 检查3: frontmatter有效
    if checks["file_exists"]:
        frontmatter = _parse_skill_md(skill_md_path)
        if frontmatter:
            checks["frontmatter_valid"] = True
            # 检查必需字段
            required_fields = ["name", "description"]
            for field in required_fields:
                if field not in frontmatter:
                    issues.append(f"缺少必需字段: {field}")
        else:
            issues.append("SKILL.md格式错误：无法解析frontmatter")
    
    # 检查4: 是否有__init__.py
    init_py = skill_dir / "__init__.py"
    if init_py.exists():
        checks["importable"] = True
    
    # 检查5: 不是骨架技能
    if skill_md_path.exists() and _is_skeleton_skill(skill_md_path):
        issues.append("技能为骨架状态，需要完整实现")
    
    valid = (
        checks["directory_exists"] and 
        checks["file_exists"] and 
        checks["frontmatter_valid"] and 
        len(issues) == 0
    )
    
    result = {
        "valid": valid,
        "skill_name": skill_name,
        "checks": checks,
        "issues": issues,
        "timestamp": datetime.now().isoformat()
    }
    
    if valid:
        logger.info(f"[SkillGenerator] Skill verified successfully: {skill_name}")
    else:
        logger.warning(f"[SkillGenerator] Skill verification failed: {skill_name} - {issues}")
    
    return result


# ========== 辅助功能 ==========

def list_all_skills() -> List[Dict[str, Any]]:
    """列出所有技能及其状态"""
    skills = []
    
    if not SKILLS_DIR.exists():
        return skills
    
    for skill_dir in SKILLS_DIR.iterdir():
        if skill_dir.is_dir() and skill_dir.name.startswith("mimiraether-"):
            skill_name = skill_dir.name.replace("mimiraether-", "")
            skill_md = skill_dir / "SKILL.md"
            
            info = {
                "name": skill_name,
                "full_name": skill_dir.name,
                "path": str(skill_dir),
                "has_skill_md": skill_md.exists(),
                "is_skeleton": _is_skeleton_skill(skill_md) if skill_md.exists() else True,
                "has_init": (skill_dir / "__init__.py").exists()
            }
            
            if skill_md.exists():
                frontmatter = _parse_skill_md(skill_md)
                if frontmatter:
                    info["version"] = frontmatter.get("version", "unknown")
                    info["description"] = frontmatter.get("description", "")[:100]
            
            skills.append(info)
    
    return sorted(skills, key=lambda x: x["name"])


def get_skill_info(skill_name: str) -> Optional[Dict[str, Any]]:
    """获取技能详细信息"""
    skill_name = skill_name.lower().strip().replace(" ", "-")
    if not skill_name.startswith("mimiraether-"):
        skill_name = f"mimiraether-{skill_name}"
    
    skill_dir = SKILLS_DIR / skill_name
    skill_md_path = skill_dir / "SKILL.md"
    
    if not skill_md_path.exists():
        return None
    
    frontmatter = _parse_skill_md(skill_md_path)
    if not frontmatter:
        return None
    
    return {
        "name": skill_name,
        "path": str(skill_dir),
        "frontmatter": frontmatter,
        "is_skeleton": _is_skeleton_skill(skill_md_path),
        "has_init": (skill_dir / "__init__.py").exists()
    }


# ========== 模块导出 ==========

__all__ = [
    "detect_gap",
    "generate_skill_md",
    "register_skill",
    "verify_skill",
    "list_all_skills",
    "get_skill_info",
    "CORE_CAPABILITIES",
]
