"""
MimirAether Skill Utils - 技能元数据工具

学习自Hermes skill_utils.py设计。

核心功能：
- 解析技能YAML frontmatter
- 平台匹配
- 禁用技能管理
- 外部技能目录管理
"""

from __future__ import annotations

import json
import os
import re
import logging
import threading
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple, Optional

# 使用mimir_constants
from agent.mimir_constants import (
    get_mimir_home,
    get_skills_dir as _get_mimir_skills_dir,
    get_skills_snapshot_path,
    ensure_initialized,
)

logger = logging.getLogger(__name__)

# ============================================================================
# 常量
# ============================================================================

PLATFORM_MAP = {
    "macos": "darwin",
    "linux": "linux",
    "windows": "win32",
}

EXCLUDED_SKILL_DIRS = frozenset((".git", ".github", ".hub"))

# 缓存
_yaml_load_fn = None


# ============================================================================
# YAML加载
# ============================================================================

def yaml_load(content: str) -> Dict[str, Any]:
    """解析YAML，优先使用CSafeLoader"""
    global _yaml_load_fn
    if _yaml_load_fn is None:
        try:
            import yaml
            loader = getattr(yaml, "CSafeLoader", None) or yaml.SafeLoader
            
            def _load(value: str):
                return yaml.load(value, Loader=loader)
            
            _yaml_load_fn = _load
        except ImportError:
            # 没有yaml，使用简单解析
            def _load(value: str):
                result = {}
                for line in value.strip().split("\n"):
                    if ":" not in line:
                        continue
                    key, val = line.split(":", 1)
                    result[key.strip()] = val.strip()
                return result
            _yaml_load_fn = _load
    return _yaml_load_fn(content)


# ============================================================================
# Frontmatter解析
# ============================================================================

def parse_frontmatter(content: str) -> Tuple[Dict[str, Any], str]:
    """
    解析markdown文件中的YAML frontmatter

    Args:
        content: markdown文件内容

    Returns:
        (frontmatter_dict, remaining_body)
    """
    frontmatter: Dict[str, Any] = {}
    body = content

    if not content.startswith("---"):
        return frontmatter, body

    # 找到第二个 ---
    end_match = re.search(r"\n---\s*\n", content[3:])
    if not end_match:
        return frontmatter, body

    yaml_content = content[3:end_match.start() + 3]
    body = content[end_match.end() + 3:]

    try:
        parsed = yaml_load(yaml_content)
        if isinstance(parsed, dict):
            frontmatter = parsed
    except Exception:
        # 回退：简单key:value解析
        for line in yaml_content.strip().split("\n"):
            if ":" not in line:
                continue
            key, value = line.split(":", 1)
            frontmatter[key.strip()] = value.strip()

    return frontmatter, body


# ============================================================================
# 平台匹配
# ============================================================================

def skill_matches_platform(frontmatter: Dict[str, Any]) -> bool:
    """
    检查技能是否匹配当前平台

    Skills declare platform requirements via a top-level ``platforms`` list::

        platforms: [macos]          # macOS only
        platforms: [macos, linux]   # macOS and Linux

    If absent or empty, skill matches **all** platforms.
    """
    import sys
    platforms = frontmatter.get("platforms")
    if not platforms:
        return True
    if not isinstance(platforms, list):
        platforms = [platforms]
    
    # 使用sys.platform ('linux', 'darwin', 'win32')
    current = sys.platform.lower()
    for platform in platforms:
        normalized = str(platform).lower().strip()
        mapped = PLATFORM_MAP.get(normalized, normalized)
        # 检查是否匹配
        if current == mapped or current.startswith(mapped) or mapped.startswith(current):
            return True
    return False


# ============================================================================
# 禁用技能管理
# ============================================================================

def get_skills_dir() -> Path:
    """获取本地技能目录
    
    优先使用MIMIR_HOME环境变量，其次使用~/.mimir/skills
    """
    ensure_initialized()
    return _get_mimir_skills_dir()


def get_config_path() -> Path:
    """获取配置文件路径
    
    使用MIMIR_HOME/config.yaml
    """
    ensure_initialized()
    from agent.mimir_constants import get_config_path as _get_mc_config_path
    return _get_mc_config_path()


def get_external_skills_dirs() -> List[Path]:
    """从config.yaml读取外部技能目录"""
    config_path = get_config_path()
    if not config_path.exists():
        return []
    
    try:
        parsed = yaml_load(config_path.read_text(encoding="utf-8"))
    except Exception:
        return []
    
    if not isinstance(parsed, dict):
        return []
    
    skills_cfg = parsed.get("skills")
    if not isinstance(skills_cfg, dict):
        return []
    
    raw_dirs = skills_cfg.get("external_dirs")
    if not raw_dirs:
        return []
    if isinstance(raw_dirs, str):
        raw_dirs = [raw_dirs]
    if not isinstance(raw_dirs, list):
        return []
    
    local_skills = get_skills_dir().resolve()
    seen: Set[Path] = set()
    result: List[Path] = []
    
    for entry in raw_dirs:
        entry = str(entry).strip()
        if not entry:
            continue
        # 展开 ~ 和环境变量
        expanded = os.path.expanduser(os.path.expandvars(entry))
        p = Path(expanded).resolve()
        if p == local_skills:
            continue
        if p in seen:
            continue
        if p.is_dir():
            seen.add(p)
            result.append(p)
        else:
            logger.debug("External skills dir does not exist, skipping: %s", p)
    
    return result


def get_all_skills_dirs() -> List[Path]:
    """返回所有技能目录：本地优先，外部其次"""
    dirs = [get_skills_dir()]
    dirs.extend(get_external_skills_dirs())
    return dirs


def _normalize_string_set(values) -> Set[str]:
    """标准化字符串集合"""
    if values is None:
        return set()
    if isinstance(values, str):
        values = [values]
    return {str(v).strip() for v in values if str(v).strip()}


def get_disabled_skill_names(platform: str | None = None) -> Set[str]:
    """读取config.yaml中的禁用技能列表"""
    config_path = get_config_path()
    if not config_path.exists():
        return set()
    
    try:
        parsed = yaml_load(config_path.read_text(encoding="utf-8"))
    except Exception as e:
        logger.debug("Could not read skill config %s: %s", config_path, e)
        return set()
    
    if not isinstance(parsed, dict):
        return set()
    
    skills_cfg = parsed.get("skills")
    if not isinstance(skills_cfg, dict):
        return set()
    
    # 尝试按平台获取禁用列表
    if platform:
        platform_disabled = (skills_cfg.get("platform_disabled") or {}).get(platform)
        if platform_disabled is not None:
            return _normalize_string_set(platform_disabled)
    
    # 回退到全局禁用列表
    return _normalize_string_set(skills_cfg.get("disabled"))


# ============================================================================
# 条件提取
# ============================================================================

def extract_skill_conditions(frontmatter: Dict[str, Any]) -> Dict[str, List]:
    """从frontmatter中提取条件激活字段"""
    metadata = frontmatter.get("metadata", {})
    if not isinstance(metadata, dict):
        metadata = {}
    hermes = metadata.get("hermes", {})
    if not isinstance(hermes, dict):
        hermes = {}
    return {
        "fallback_for_toolsets": hermes.get("fallback_for_toolsets", []),
        "requires_toolsets": hermes.get("requires_toolsets", []),
        "fallback_for_tools": hermes.get("fallback_for_tools", []),
        "requires_tools": hermes.get("requires_tools", []),
    }


# ============================================================================
# 技能配置变量
# ============================================================================

def extract_skill_config_vars(frontmatter: Dict[str, Any]) -> List[Dict[str, Any]]:
    """从frontmatter中提取配置变量声明"""
    metadata = frontmatter.get("metadata", {})
    if not isinstance(metadata, dict):
        return []
    
    hermes = metadata.get("hermes", {})
    if not isinstance(hermes, dict):
        return []
    
    config = hermes.get("config")
    if not config:
        return []
    if not isinstance(config, list):
        config = [config]
    
    result = []
    for item in config:
        if not isinstance(item, dict):
            continue
        key = item.get("key")
        if not key:
            continue
        result.append({
            "key": key,
            "description": item.get("description", ""),
            "default": item.get("default", ""),
            "prompt": item.get("prompt", ""),
        })
    
    return result


# ============================================================================
# 技能发现
# ============================================================================

def discover_skills(skills_dir: Path) -> List[Dict[str, Any]]:
    """发现目录中的所有技能"""
    skills = []
    
    if not skills_dir.exists():
        return skills
    
    for item in skills_dir.iterdir():
        if item.is_dir() and item.name not in EXCLUDED_SKILL_DIRS:
            skill_file = item / "SKILL.md"
            if skill_file.exists():
                try:
                    content = skill_file.read_text(encoding="utf-8")
                    frontmatter, _ = parse_frontmatter(content)
                    
                    # 平台过滤
                    if not skill_matches_platform(frontmatter):
                        continue
                    
                    skills.append({
                        "name": item.name,
                        "path": str(skill_file),
                        "frontmatter": frontmatter,
                        "enabled": True,
                    })
                except Exception as e:
                    logger.debug("Failed to read skill %s: %s", skill_file, e)
    
    return skills


def find_skill_by_name(name: str) -> Path | None:
    """
    Find a skill directory by name across all skills dirs.

    Ported from: hermes-agent/agent/skill_utils.find_skill_by_name()

    Args:
        name: Skill directory name (not full path)

    Returns:
        Path to skill directory if found, None otherwise
    """
    for skills_dir in get_all_skills_dirs():
        if not skills_dir.exists():
            continue
        for skill_md in skills_dir.rglob("SKILL.md"):
            if skill_md.parent.name == name:
                return skill_md.parent
    return None


# ============================================================================
# Hermès兼容函数
# ============================================================================

# Storage prefix for skill config vars in config.yaml
SKILL_CONFIG_PREFIX = "skills.config"


def iter_skill_index_files(skills_dir: Path, filename: str):
    """遍历skills_dir，返回匹配*filename的排序路径（Hermès兼容）

    排除``.git``, ``.github``, ``.hub``目录。
    """
    matches = []
    for root, dirs, files in os.walk(skills_dir):
        dirs[:] = [d for d in dirs if d not in EXCLUDED_SKILL_DIRS]
        for f in files:
            if f == filename:
                matches.append(Path(root) / f)
    return sorted(matches)


def extract_skill_description(frontmatter: Dict[str, Any]) -> str:
    """从解析的frontmatter中提取截断的描述（Hermès兼容）"""
    raw_desc = frontmatter.get("description", "")
    if not raw_desc:
        return ""
    desc = str(raw_desc).strip().strip("'\"")
    if len(desc) > 60:
        return desc[:57] + "..."
    return desc


def _resolve_dotpath(config: Dict[str, Any], dotted_key: str) -> Any:
    """遍历嵌套dict，按照点分key路径查找（Hermès兼容）"""
    parts = dotted_key.split(".")
    current = config
    for part in parts:
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            return None
    return current


def resolve_skill_config_values(
    config_vars: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """从config.yaml解析skill config vars的当前值（Hermès兼容）

    Skill config存储在config.yaml的``skills.config.<key>``下。
    返回映射到逻辑key（skill声明的）及其当前值的dict。
    """
    config_path = get_config_path()
    config: Dict[str, Any] = {}
    if config_path.exists():
        try:
            parsed = yaml_load(config_path.read_text(encoding="utf-8"))
            if isinstance(parsed, dict):
                config = parsed
        except Exception:
            pass

    resolved: Dict[str, Any] = {}
    for var in config_vars:
        logical_key = var["key"]
        storage_key = f"{SKILL_CONFIG_PREFIX}.{logical_key}"
        value = _resolve_dotpath(config, storage_key)

        if value is None or (isinstance(value, str) and not value.strip()):
            value = var.get("default", "")

        # 展开path值中的~
        if isinstance(value, str) and ("~" in value or "${" in value):
            value = os.path.expanduser(os.path.expandvars(value))

        resolved[logical_key] = value

    return resolved


def discover_all_skill_config_vars() -> List[Dict[str, Any]]:
    """扫描所有启用的skills并收集它们的config变量声明（Hermès兼容）

    遍历每个skills目录，解析每个SKILL.md frontmatter，
    返回去重的config var dict列表。
    每个dict还包含一个``skill`` key用于归属。
    """
    all_vars: List[Dict[str, Any]] = []
    seen_keys: set = set()

    disabled = get_disabled_skill_names()
    for skills_dir in get_all_skills_dirs():
        if not skills_dir.is_dir():
            continue
        for skill_file in iter_skill_index_files(skills_dir, "SKILL.md"):
            try:
                raw = skill_file.read_text(encoding="utf-8")
                frontmatter, _ = parse_frontmatter(raw)
            except Exception:
                continue

            skill_name = frontmatter.get("name") or skill_file.parent.name
            if str(skill_name) in disabled:
                continue
            if not skill_matches_platform(frontmatter):
                continue

            config_vars = extract_skill_config_vars(frontmatter)
            for var in config_vars:
                if var["key"] not in seen_keys:
                    var["skill"] = str(skill_name)
                    all_vars.append(var)
                    seen_keys.add(var["key"])

    return all_vars


# ============================================================================
# 测试
# ============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("Skill Utils 测试")
    print("=" * 60)

    # 测试1: parse_frontmatter
    print("\n[测试1] parse_frontmatter")
    content = """---
name: test-skill
description: A test skill
platforms: [linux, darwin]
---

# Skill Body
"""
    frontmatter, body = parse_frontmatter(content)
    assert frontmatter["name"] == "test-skill"
    assert "Skill Body" in body
    print(f"  frontmatter: {frontmatter}")
    print(f"  body preview: {body[:20]}...")
    print("  ✅ 通过")

    # 测试2: parse_frontmatter (无frontmatter)
    print("\n[测试2] parse_frontmatter (无)")
    content2 = "# Just a header\n\nSome content"
    fm, body2 = parse_frontmatter(content2)
    assert fm == {}
    assert "Some content" in body2
    print("  ✅ 通过")

    # 测试3: skill_matches_platform
    print("\n[测试3] skill_matches_platform")
    assert skill_matches_platform({}) == True  # 无限制
    assert skill_matches_platform({"platforms": []}) == True  # 空列表
    assert skill_matches_platform({"platforms": ["linux"]}) == True  # 匹配
    print(f"  当前平台: {os.name}")
    print("  ✅ 通过")

    # 测试4: _normalize_string_set
    print("\n[测试4] _normalize_string_set")
    assert _normalize_string_set(None) == set()
    assert _normalize_string_set("a") == {"a"}
    assert _normalize_string_set(["a", "b"]) == {"a", "b"}
    print(f"  结果: {_normalize_string_set(['x', 'y'])}")
    print("  ✅ 通过")

    # 测试5: extract_skill_conditions
    print("\n[测试5] extract_skill_conditions")
    fm = {
        "metadata": {
            "hermes": {
                "requires_toolsets": ["coding"],
                "fallback_for_tools": ["search"],
            }
        }
    }
    conditions = extract_skill_conditions(fm)
    assert conditions["requires_toolsets"] == ["coding"]
    assert conditions["fallback_for_tools"] == ["search"]
    print(f"  conditions: {conditions}")
    print("  ✅ 通过")

    # 测试6: extract_skill_config_vars
    print("\n[测试6] extract_skill_config_vars")
    fm2 = {
        "metadata": {
            "hermes": {
                "config": [
                    {"key": "api.key", "description": "API Key", "default": ""},
                    {"key": "debug", "description": "Debug mode", "default": "false"},
                ]
            }
        }
    }
    vars = extract_skill_config_vars(fm2)
    assert len(vars) == 2
    assert vars[0]["key"] == "api.key"
    print(f"  config vars: {[v['key'] for v in vars]}")
    print("  ✅ 通过")

    # 测试7: get_skills_dir
    print("\n[测试7] get_skills_dir")
    skills_dir = get_skills_dir()
    assert skills_dir.exists()
    print(f"  skills_dir: {skills_dir}")
    print("  ✅ 通过")

    # 测试8: discover_skills
    print("\n[测试8] discover_skills")
    skills = discover_skills(skills_dir)
    print(f"  发现技能数: {len(skills)}")
    if skills:
        print(f"  示例: {[s['name'] for s in skills[:3]]}")
    print("  ✅ 通过")

    # 测试9: get_disabled_skill_names
    print("\n[测试9] get_disabled_skill_names")
    disabled = get_disabled_skill_names()
    print(f"  禁用技能: {disabled}")
    print("  ✅ 通过")

    # 测试10: yaml_load (无yaml库时的回退)
    print("\n[测试10] yaml_load回退")
    import sys
    # 临时移除yaml
    orig_yaml = sys.modules.get("yaml")
    sys.modules["yaml"] = None
    try:
        result = yaml_load("key: value\nname: test")
        assert result.get("key") == "value"
        print(f"  yaml_load回退结果: {result}")
    finally:
        if orig_yaml:
            sys.modules["yaml"] = orig_yaml
        else:
            del sys.modules["yaml"]
    print("  ✅ 通过")

    print("\n" + "=" * 60)
    print("所有测试通过!")
    print("=" * 60)

# ============================================================================
# Skills Prompt Snapshot System
# ============================================================================
# 学习自Hermes: 磁盘缓存skills prompt以加速冷启动

_SKILLS_PROMPT_SNAPSHOT_VERSION = 1
_SKILLS_PROMPT_SNAPSHOT_MAX = 8
_SKILLS_PROMPT_SNAPSHOT: "OrderedDict[tuple, str]" = None  # type: ignore
_SKILLS_PROMPT_SNAPSHOT_LOCK = threading.Lock()


def _get_skills_prompt_snapshot_cache():
    """获取或创建snapshot缓存"""
    global _SKILLS_PROMPT_SNAPSHOT
    if _SKILLS_PROMPT_SNAPSHOT is None:
        from collections import OrderedDict
        _SKILLS_PROMPT_SNAPSHOT = OrderedDict()
    return _SKILLS_PROMPT_SNAPSHOT


def _build_skills_manifest(skills_dir: Path) -> Dict[str, List[int]]:
    """构建所有SKILL.md和DESCRIPTION.md文件的mtime/size manifest"""
    manifest: Dict[str, List[int]] = {}
    for filename in ("SKILL.md", "DESCRIPTION.md"):
        for path in iter_skill_index_files(skills_dir, filename):
            try:
                st = path.stat()
                manifest[str(path.relative_to(skills_dir))] = [st.st_mtime_ns, st.st_size]
            except OSError:
                continue
    return manifest


def _load_skills_snapshot(skills_dir: Path) -> Optional[Dict]:
    """从磁盘加载snapshot，如果manifest匹配则使用"""
    snapshot_path = get_skills_snapshot_path()
    if not snapshot_path.exists():
        return None
    try:
        snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(snapshot, dict):
        return None
    if snapshot.get("version") != _SKILLS_PROMPT_SNAPSHOT_VERSION:
        return None
    if snapshot.get("manifest") != _build_skills_manifest(skills_dir):
        return None
    return snapshot


def _write_skills_snapshot(
    skills_dir: Path,
    manifest: Dict[str, List[int]],
    skill_entries: List[Dict],
    category_descriptions: Dict[str, str],
) -> None:
    """将snapshot持久化到磁盘用于快速冷启动"""
    payload = {
        "version": _SKILLS_PROMPT_SNAPSHOT_VERSION,
        "manifest": manifest,
        "skills": skill_entries,
        "category_descriptions": category_descriptions,
    }
    try:
        from utils import atomic_json_write
        atomic_json_write(get_skills_snapshot_path(), payload)
    except ImportError:
        # 回退：直接写入
        snapshot_path = get_skills_snapshot_path()
        snapshot_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    except Exception as e:
        logger.debug("Could not write skills prompt snapshot: %s", e)


def _build_snapshot_entry(
    skill_file: Path,
    skills_dir: Path,
    frontmatter: Dict[str, Any],
    description: str,
) -> Dict:
    """为单个skill构建可序列化的元数据dict"""
    rel_path = skill_file.relative_to(skills_dir)
    parts = rel_path.parts
    category = parts[0] if len(parts) >= 2 else "uncategorized"
    return {
        "name": skill_file.parent.name,
        "category": category,
        "description": description,
        "path": str(rel_path),
        "frontmatter": {
            k: v for k, v in frontmatter.items()
            if k in ("name", "description", "platforms", "always_apply")
        },
    }


def clear_skills_system_prompt_cache(*, clear_snapshot: bool = False) -> None:
    """清除内存中的skills prompt缓存（可选清除磁盘snapshot）"""
    cache = _get_skills_prompt_snapshot_cache()
    with _SKILLS_PROMPT_SNAPSHOT_LOCK:
        cache.clear()
    if clear_snapshot:
        try:
            get_skills_snapshot_path().unlink(missing_ok=True)
        except OSError as e:
            logger.debug("Could not remove skills prompt snapshot: %s", e)


def get_skills_for_system_prompt(
    skills_dir: Optional[Path] = None,
    disabled_names: Optional[Set[str]] = None,
    categories: Optional[Dict[str, str]] = None,
) -> Tuple[List[Dict], Dict[str, str]]:
    """
    获取用于system prompt的skills列表
    
    优先使用磁盘snapshot加速冷启动，
    当snapshot过期时重新扫描并更新。
    
    Returns:
        (skill_entries, category_descriptions)
    """
    if skills_dir is None:
        skills_dir = get_skills_dir()
    
    if not skills_dir.exists():
        return [], {}
    
    if disabled_names is None:
        disabled_names = get_disabled_skill_names()
    
    if categories is None:
        categories = {}
    
    # 尝试从磁盘加载snapshot
    snapshot = _load_skills_snapshot(skills_dir)
    if snapshot:
        logger.debug("Using cached skills snapshot")
        return snapshot.get("skills", []), snapshot.get("category_descriptions", {})
    
    # 构建新的manifest和entries
    manifest = _build_skills_manifest(skills_dir)
    skill_entries: List[Dict] = []
    seen_categories: Set[str] = set()
    
    for skill_file in iter_skill_index_files(skills_dir, "SKILL.md"):
        try:
            raw = skill_file.read_text(encoding="utf-8")
            frontmatter, body = parse_frontmatter(raw)
        except Exception:
            continue
        
        name = str(skill_file.parent.name)
        if name in disabled_names:
            continue
        
        if not skill_matches_platform(frontmatter):
            continue
        
        description = extract_skill_description(frontmatter)
        entry = _build_snapshot_entry(skill_file, skills_dir, frontmatter, description)
        skill_entries.append(entry)
        
        # 收集category描述
        category = entry["category"]
        if category not in seen_categories:
            seen_categories.add(category)
            cat_desc = frontmatter.get("category_description", "")
            if cat_desc:
                categories[category] = cat_desc
    
    # 写入磁盘snapshot
    _write_skills_snapshot(skills_dir, manifest, skill_entries, categories)
    
    return skill_entries, categories
