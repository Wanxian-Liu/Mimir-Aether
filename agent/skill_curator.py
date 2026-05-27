"""
MimirAether Skill Curator — 技能生命周期管理

三层生命周期：
  fresh   — 活跃中
  stale   — 30天未触，提醒
  dormant — 60天未触，待胶囊化

设计原则：
  - 复用 data/persistent.json，不加新基础设施
  - 单文件，~300行
  - 知识永不删除——dormant 前胶囊化（Phase 2）
"""

import logging
import os
import threading
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from agent import persistent_store

logger = logging.getLogger(__name__)

# ── 配置 ────────────────────────────────────────────────────────────────────
SKILLS_ROOT = Path(__file__).resolve().parent.parent / "skills"
SKILL_FILENAME = "SKILL.md"

STALE_THRESHOLD_DAYS = 30
DORMANT_THRESHOLD_DAYS = 60
DORMANT_DIR = ".dormant"

# ── SkillStatus ─────────────────────────────────────────────────────────────

class SkillStatus:
    FRESH = "fresh"
    STALE = "stale"
    DORMANT = "dormant"


# ── 内部辅助 ────────────────────────────────────────────────────────────────

def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _parse_frontmatter(content: str) -> dict:
    """从 SKILL.md 提取 YAML frontmatter。"""
    import re
    import yaml as _yaml
    match = re.match(r'^---\s*\n(.*?)\n---', content, re.DOTALL)
    if match:
        try:
            return _yaml.safe_load(match.group(1)) or {}
        except _yaml.YAMLError:
            pass
    return {}


def _collect_skill_roots() -> List[Path]:
    """Repo skills/ plus MIMIR home and configured external dirs (HERM-CUR-02)."""
    roots: List[Path] = []
    seen: set[Path] = set()

    def _add(path: Path) -> None:
        try:
            resolved = path.resolve()
        except OSError:
            return
        if resolved in seen or not path.is_dir():
            return
        seen.add(resolved)
        roots.append(path)

    _add(SKILLS_ROOT)
    try:
        from agent.mimir_constants import get_skills_dir

        _add(get_skills_dir())
    except Exception:
        pass
    try:
        from agent.skill_utils import get_external_skills_dirs

        for ext in get_external_skills_dirs():
            _add(ext)
    except Exception:
        pass
    return roots


def _discover_skills_in_root(root: Path) -> List[Tuple[str, Path, dict]]:
    """Scan one skills root (category/skill or flat skill dir)."""
    results: List[Tuple[str, Path, dict]] = []
    if not root.is_dir():
        return results

    skip_names = {"__pycache__", "modules", "data", DORMANT_DIR}

    for item in sorted(root.iterdir()):
        if not item.is_dir() or item.name.startswith(".") or item.name in skip_names:
            continue
        direct_skill = item / SKILL_FILENAME
        if direct_skill.exists():
            try:
                content = direct_skill.read_text(encoding="utf-8")
                fm = _parse_frontmatter(content)
                name = str(fm.get("name", item.name))
                results.append((name, item, fm))
            except OSError:
                pass
            continue
        for sub in sorted(item.iterdir()):
            if not sub.is_dir() or sub.name.startswith("."):
                continue
            skill_file = sub / SKILL_FILENAME
            if not skill_file.exists():
                continue
            try:
                content = skill_file.read_text(encoding="utf-8")
                fm = _parse_frontmatter(content)
                name = str(fm.get("name", sub.name))
                results.append((name, sub, fm))
            except OSError:
                continue
    return results


def _discover_skills() -> List[Tuple[str, Path, dict]]:
    """
    扫描所有技能根目录下的 SKILL.md。

    Returns: [(name, dir, frontmatter), ...]
    """
    by_name: Dict[str, Tuple[str, Path, dict]] = {}
    for root in _collect_skill_roots():
        for name, skill_dir, fm in _discover_skills_in_root(root):
            if name not in by_name:
                by_name[name] = (name, skill_dir, fm)
    return list(by_name.values())


def scan_all_skills() -> List[dict]:
    """Full lifecycle scan across all skill roots (HERM-CUR-02)."""
    return scan_skills()


def build_lifecycle_report(
    skills: List[dict],
    buckets: Dict[str, List[dict]],
    actions_data: Optional[dict] = None,
) -> str:
    """Markdown lifecycle report capped at 2KB for logs / mimir_ops."""
    if actions_data is None:
        actions_data = curator_actions()
    summary = actions_data.get("summary", {})
    lines = [
        "# Skill Curator lifecycle pass",
        "",
        f"- total: {len(skills)}",
        f"- fresh: {len(buckets.get('fresh', []))}",
        f"- stale: {len(buckets.get('stale', []))}",
        f"- dormant: {len(buckets.get('dormant', []))}",
        f"- archived registry (`.dormant/`): see `{DORMANT_DIR}/`",
        "",
        "## Merge / review suggestions",
    ]
    for action in actions_data.get("actions", [])[:25]:
        lines.append(
            f"- **{action.get('action')}** `{action.get('name')}`: {action.get('reason')}"
        )
    if not actions_data.get("actions"):
        lines.append("- (none)")
    text = "\n".join(lines)
    encoded = text.encode("utf-8")
    if len(encoded) > 2048:
        text = encoded[:2000].decode("utf-8", errors="ignore") + "\n…(truncated)"
    return text


def run_lifecycle_pass() -> Dict[str, Any]:
    """
    Periodic lifecycle scan: all skill roots, persist skill_usage hints, emit report.
    """
    skills = scan_skills()
    usage = _get_usage()
    updated = dict(usage)
    for row in skills:
        name = row["name"]
        last = row.get("last_touched")
        if name and last and last != "unknown" and name not in updated:
            updated[name] = str(last)
    if updated != usage:
        _set_usage(updated)

    buckets = assess_staleness(skills)
    actions_data = curator_actions()
    report_md = build_lifecycle_report(skills, buckets, actions_data)
    logger.info("skill_curator lifecycle pass (%d skills)\n%s", len(skills), report_md)

    return {
        "total": len(skills),
        "stale": buckets.get("stale", []),
        "dormant": buckets.get("dormant", []),
        "report_md": report_md,
        "actions_summary": actions_data.get("summary", {}),
    }


def schedule_skill_curator_lifecycle_pass(
    *,
    session_id: str = "",
    task_name: str = "",
) -> None:
    """Fire-and-forget lifecycle pass when MIMIR_SKILL_CURATOR_ON_CLOSE=1."""
    if os.environ.get("MIMIR_SKILL_CURATOR_ON_CLOSE", "").strip().lower() not in (
        "1",
        "true",
        "yes",
    ):
        return

    def _worker() -> None:
        try:
            run_lifecycle_pass()
        except Exception as exc:
            logger.warning(
                "skill_curator lifecycle pass failed session_id=%s: %s",
                session_id,
                exc,
            )

    threading.Thread(
        target=_worker,
        daemon=True,
        name="skill-curator-lifecycle",
    ).start()


# ── Usage Tracking ──────────────────────────────────────────────────────────

def _get_usage() -> Dict[str, str]:
    """从 persistent.json 读取 skill_usage 段。读取失败时返回空 dict。"""
    try:
        data = persistent_store.load()
        return data.get("skill_usage", {})
    except RuntimeError as e:
        logger.warning("Cannot track skill usage: %s", e)
        return {}


def _set_usage(usage: Dict[str, str]) -> None:
    """写入 skill_usage 到 persistent.json。读取/写入失败时仅记录日志。"""
    try:
        persistent_store.read_modify_write(
            lambda data: data.__setitem__("skill_usage", usage)
        )
    except (RuntimeError, ValueError) as e:
        logger.warning("Failed to persist skill_usage: %s", e)


def touch_skill(name: str) -> None:
    """
    记录技能被触碰（skill_view 调用时触发）。

    在 agent/skill_funcs.py 的 skill_view_func() 里调用本函数。

    触碰是非关键操作：persistent.json 损坏时静默跳过，
    skill_view 本身不受影响。
    """
    try:
        usage = _get_usage()
        usage[name] = _now_utc().isoformat()
        _set_usage(usage)
    except Exception as e:
        logger.warning("touch_skill(%s) failed (non-critical): %s", name, e)


# ── 扫描 & 评估 ─────────────────────────────────────────────────────────────

def scan_skills() -> List[dict]:
    """
    扫描所有技能，附加上次触碰时间和状态。

    Returns:
        [{name, category, last_touched, days_since, status}, ...]
    """
    usage = _get_usage()
    now = _now_utc()
    skills = _discover_skills()
    results = []

    for name, skill_dir, fm in skills:
        category = str(skill_dir.parent.name) if skill_dir.parent != SKILLS_ROOT else "root"
        last_ts = usage.get(name, "")

        if last_ts:
            try:
                last_dt = datetime.fromisoformat(last_ts)
                days_since = (now - last_dt).days
                last_touched = last_dt.isoformat()
            except ValueError:
                days_since = None
                last_touched = last_ts
        else:
            # 从未被触碰——用文件修改时间作为初始参考
            skill_file = skill_dir / SKILL_FILENAME
            if skill_file.exists():
                mtime = skill_file.stat().st_mtime
                last_dt = datetime.fromtimestamp(mtime, tz=timezone.utc)
                days_since = (now - last_dt).days
                last_touched = last_dt.isoformat()
            else:
                days_since = None
                last_touched = "unknown"

        # 判断状态
        if days_since is None:
            status = SkillStatus.FRESH  # 无法判断，保守
        elif days_since >= DORMANT_THRESHOLD_DAYS:
            status = SkillStatus.DORMANT
        elif days_since >= STALE_THRESHOLD_DAYS:
            status = SkillStatus.STALE
        else:
            status = SkillStatus.FRESH

        results.append({
            "name": name,
            "category": category,
            "last_touched": last_touched if isinstance(last_touched, str) else last_touched.isoformat() if hasattr(last_touched, 'isoformat') else str(last_touched),
            "days_since": days_since if days_since is not None else "unknown",
            "status": status,
        })

    return results


def assess_staleness(skills: List[dict] = None) -> Dict[str, List[dict]]:
    """
    按状态分类。

    Returns:
        {fresh: [...], stale: [...], dormant: [...]}
    """
    if skills is None:
        skills = scan_skills()

    buckets = {"fresh": [], "stale": [], "dormant": []}
    for s in skills:
        buckets.setdefault(s["status"], []).append(s)
    return buckets


# ── 胶囊化 & 沉寂 ───────────────────────────────────────────────────────────

def _get_dormant_root() -> Path:
    """skills/.dormant/ 绝对路径。"""
    return SKILLS_ROOT / DORMANT_DIR


def _get_dormant_registry() -> dict:
    """从 persistent.json 读取 dormant_skills 段。读取失败时返回空 dict。"""
    try:
        data = persistent_store.load()
        return data.get("dormant_skills", {})
    except RuntimeError as e:
        logger.warning("Cannot read dormant registry: %s", e)
        return {}


def _save_dormant_registry(registry: dict) -> None:
    """写入 dormant_skills 到 persistent.json。失败时仅记录日志。"""
    try:
        persistent_store.read_modify_write(
            lambda data: data.__setitem__("dormant_skills", registry)
        )
    except (RuntimeError, ValueError) as e:
        logger.warning("Failed to persist dormant_skills: %s", e)


def _find_dormant_skill(name: str) -> Optional[Path]:
    """
    在 .dormant/ 下查找沉寂技能目录。

    Returns:
        Path 或 None
    """
    dormant_root = _get_dormant_root()
    if not dormant_root.exists():
        return None

    for item in dormant_root.iterdir():
        if not item.is_dir():
            continue
        for sub in item.iterdir():
            if sub.is_dir() and sub.name == name:
                return sub
    return None


def capsulize_and_dormant(name: str) -> dict:
    """
    将技能胶囊化并移入 .dormant/。

    操作：
      1. 读取 SKILL.md，提取 frontmatter + 前 2000 字符
      2. 生成 capsule.md（本地知识胶囊）
      3. 移动技能目录到 skills/.dormant/<category>/<name>/
      4. 记录到 persistent.json

    Returns:
        {success, name, capsule_path?, error?}
    """
    import shutil

    # 1. 找到技能
    skill_info = None
    for s in scan_skills():
        if s["name"] == name:
            skill_info = s
            break

    # 也可能已经在 dormant 里
    skill_dir = None
    for nm, sd, fm in _discover_skills():
        if nm == name:
            skill_dir = sd
            break

    if skill_dir is None:
        skill_dir = _find_dormant_skill(name)

    if skill_dir is None:
        return {"success": False, "error": f"Skill not found: {name}"}

    # 2. 读取 SKILL.md
    skill_file = skill_dir / SKILL_FILENAME
    if not skill_file.exists():
        return {"success": False, "error": f"SKILL.md not found for: {name}"}

    try:
        content = skill_file.read_text(encoding="utf-8")
    except OSError as e:
        return {"success": False, "error": str(e)}

    fm = _parse_frontmatter(content)
    description = fm.get("description", "")

    # 提取正文（去掉 frontmatter）
    import re
    body_match = re.match(r'^---\s*\n.*?\n---\s*\n(.*)', content, re.DOTALL)
    body = body_match.group(1).strip() if body_match else content.strip()
    # 取前 2000 字符作为摘要
    excerpt = body[:2000]
    if len(body) > 2000:
        excerpt += "\n\n... (truncated)"

    # 3. 确定原始分类
    category = skill_info["category"] if skill_info else str(skill_dir.parent.name)
    if category == DORMANT_DIR:
        # 从 dormant registry 中恢复原始分类
        reg = _get_dormant_registry()
        entry = reg.get(name, {})
        category = entry.get("original_category", "unknown")

    # 4. 生成胶囊文件
    now = _now_utc().isoformat()
    capsule_content = f"""# [DORMANT] {name}

**沉寂时间**: {now}
**原始分类**: {category}
**描述**: {description}
**触发阈值**: {DORMANT_THRESHOLD_DAYS}天未触碰

---

## 技能要点

{excerpt}

---

> 此胶囊由 Skill Curator 自动生成。原始技能已移入 .dormant/。
> 调用 `skill_view("{name}")` 即可自动唤醒。
"""

    # 5. 创建 .dormant/ 目录并移动技能
    dormant_root = _get_dormant_root()
    dormant_dir = dormant_root / category / name
    dormant_dir.parent.mkdir(parents=True, exist_ok=True)

    # 先移动原技能目录
    try:
        if skill_dir.parent.name == DORMANT_DIR:
            # 已经在 dormant 里
            pass
        elif skill_dir != dormant_dir:
            shutil.move(str(skill_dir), str(dormant_dir))
    except OSError as e:
        return {"success": False, "error": f"Move failed: {e}"}

    # 再写胶囊到移动后的目录里
    capsule_file = dormant_dir / "capsule.md"
    capsule_file.write_text(capsule_content, encoding="utf-8")

    # 7. 记录到 registry
    reg = _get_dormant_registry()
    reg[name] = {
        "capsule_path": str(dormant_dir.relative_to(SKILLS_ROOT)),
        "original_category": category,
        "dormant_at": now,
        "summary": description,
    }
    _save_dormant_registry(reg)

    logger.info("Skill %s capsulized → dormant (category=%s)", name, category)
    return {
        "success": True,
        "name": name,
        "capsule_path": str(dormant_dir.relative_to(SKILLS_ROOT)),
    }


def revive_skill(name: str) -> dict:
    """
    从 .dormant/ 唤醒技能。

    操作：
      1. 在 .dormant/ 下找到技能
      2. 移回原始分类目录
      3. 更新 persistent.json（移除 dormant 记录，重置触碰时间）

    Returns:
        {success, name, restored_to?, error?}
    """
    import shutil

    # 1. 查找
    dormant_dir = _find_dormant_skill(name)
    if dormant_dir is None:
        return {"success": False, "error": f"Dormant skill not found: {name}"}

    # 2. 确定目标位置
    reg = _get_dormant_registry()
    entry = reg.get(name, {})
    category = entry.get("original_category", dormant_dir.parent.name)
    target_dir = SKILLS_ROOT / category / name

    # 如果目标已存在（不该发生，但防冲突）
    if target_dir.exists():
        return {"success": False, "error": f"Target already exists: {target_dir}"}

    # 3. 移动
    target_dir.parent.mkdir(parents=True, exist_ok=True)
    try:
        shutil.move(str(dormant_dir), str(target_dir))
    except OSError as e:
        return {"success": False, "error": f"Move failed: {e}"}

    # 4. 清理 registry
    if name in reg:
        del reg[name]
        _save_dormant_registry(reg)

    # 5. 重置触碰时间（复活即触碰）
    touch_skill(name)

    # 6. 清理空的父目录
    try:
        parent = dormant_dir.parent
        if parent != _get_dormant_root() and not any(parent.iterdir()):
            parent.rmdir()
    except OSError:
        pass

    logger.info("Skill %s revived from dormant → %s", name, category)
    return {"success": True, "name": name, "restored_to": str(target_dir)}


# ── 行动建议 ────────────────────────────────────────────────────────────────

class CuratorAction:
    KEEP = "keep"
    REVIEW = "review"
    PRE_CAPSULIZE = "pre_capsulize"
    CAPSULIZE_NOW = "capsulize_now"


def _read_skill_meta(name: str) -> dict:
    """
    读取技能元数据用于策展判断。

    Returns:
        {body_len, body, has_placeholders, is_auto_load, description_len}
    """
    import re

    info: dict[str, object] = {
        "body_len": 0,
        "body": "",
        "has_placeholders": False,
        "is_auto_load": False,
        "description_len": 0,
    }

    for _, skill_dir, fm in _discover_skills():
        if fm.get("name") == name or skill_dir.name == name:
            skill_file = skill_dir / SKILL_FILENAME
            if not skill_file.exists():
                break
            try:
                content = skill_file.read_text(encoding="utf-8")
            except OSError:
                break

            info["description_len"] = len(fm.get("description", ""))

            body_match = re.match(r'^---\s*\n.*?\n---\s*\n(.*)', content, re.DOTALL)
            body = body_match.group(1).strip() if body_match else content.strip()
            info["body"] = body
            info["body_len"] = len(body)

            # 占位符检测
            placeholder_markers = [
                "TODO", "TODO:", "TBD", "待实现", "待完善", "待完成",
                "Not yet implemented", "Work in progress",
            ]
            info["has_placeholders"] = any(
                m.lower() in body[:1000].lower() for m in placeholder_markers
            )

            # auto_load 检测
            auto_load_meta = fm.get("auto_load_meta", {})
            info["is_auto_load"] = bool(fm.get("auto_load") or auto_load_meta.get("triggers"))
            break

    return info


def curator_actions() -> dict:
    """
    生成可执行的策展行动清单。

    每个行动包含:
      {name, action, reason, days_since, body_len, description_len}

    Returns:
        {actions: [...], summary: {...}}
    """
    skills = scan_skills()
    buckets = assess_staleness(skills)

    actions: list[dict] = []

    # ── dormant → capsulize_now ──
    for s in buckets.get("dormant", []):
        meta = _read_skill_meta(s["name"])
        actions.append({
            "name": s["name"],
            "action": CuratorAction.CAPSULIZE_NOW,
            "reason": "已达休眠阈值(60+天)，知识应胶囊化保留",
            "days_since": s["days_since"],
            "body_len": meta["body_len"],
            "description_len": meta["description_len"],
        })

    # ── stale → 分类 ──
    for s in buckets.get("stale", []):
        meta = _read_skill_meta(s["name"])
        days = s["days_since"]

        if days >= DORMANT_THRESHOLD_DAYS - 7:
            # 53-59天：预警
            actions.append({
                "name": s["name"],
                "action": CuratorAction.PRE_CAPSULIZE,
                "reason": f"距休眠阈值仅剩{DORMANT_THRESHOLD_DAYS - days}天，建议近期复核",
                "days_since": days,
                "body_len": meta["body_len"],
                "description_len": meta["description_len"],
            })
        elif meta["body_len"] < 400 or meta["has_placeholders"] or meta["description_len"] < 30:
            # 内容单薄 → review
            detail_parts = []
            if meta["body_len"] < 400:
                detail_parts.append(f"内容仅{meta['body_len']}字")
            if meta["has_placeholders"]:
                detail_parts.append("含待实现占位符")
            if meta["description_len"] < 30:
                detail_parts.append("描述过短")

            actions.append({
                "name": s["name"],
                "action": CuratorAction.REVIEW,
                "reason": "质量存疑: " + "; ".join(detail_parts),
                "days_since": days,
                "body_len": meta["body_len"],
                "description_len": meta["description_len"],
            })
        else:
            # 内容充实 → 保留
            actions.append({
                "name": s["name"],
                "action": CuratorAction.KEEP,
                "reason": f"内容充实({meta['body_len']}字)但低频使用",
                "days_since": days,
                "body_len": meta["body_len"],
                "description_len": meta["description_len"],
            })

    # 按行动类型 + 天数排序
    order = {
        CuratorAction.CAPSULIZE_NOW: 0,
        CuratorAction.PRE_CAPSULIZE: 1,
        CuratorAction.REVIEW: 2,
        CuratorAction.KEEP: 3,
    }
    actions.sort(key=lambda a: (
        order.get(a["action"], 99),
        -(a["days_since"] if isinstance(a["days_since"], int) else 0),
    ))

    return {
        "actions": actions,
        "summary": {
            "total_skills": len(skills),
            "total_actions": len(actions),
            "by_action": {
                CuratorAction.CAPSULIZE_NOW: sum(1 for a in actions if a["action"] == CuratorAction.CAPSULIZE_NOW),
                CuratorAction.PRE_CAPSULIZE: sum(1 for a in actions if a["action"] == CuratorAction.PRE_CAPSULIZE),
                CuratorAction.REVIEW: sum(1 for a in actions if a["action"] == CuratorAction.REVIEW),
                CuratorAction.KEEP: sum(1 for a in actions if a["action"] == CuratorAction.KEEP),
            },
        },
    }


def curator_actions_report() -> str:
    """curator_actions() 的人类可读格式化输出。"""
    data = curator_actions()
    actions = data["actions"]
    summary = data["summary"]

    if not actions:
        return "📋 技能策展: 无需行动。所有技能状态正常。"

    lines = [
        "═" * 50,
        "  📋 Skill Curator 行动清单",
        "═" * 50,
        f"  总计 {summary['total_skills']} 技能 | 待行动 {summary['total_actions']}",
        f"  🔴 胶囊化: {summary['by_action'].get('capsulize_now', 0)}",
        f"  🟡 预警: {summary['by_action'].get('pre_capsulize', 0)}",
        f"  🟠 复核: {summary['by_action'].get('review', 0)}",
        f"  🟢 保留: {summary['by_action'].get('keep', 0)}",
        "",
    ]

    icons = {
        CuratorAction.CAPSULIZE_NOW: "🔴",
        CuratorAction.PRE_CAPSULIZE: "🟡",
        CuratorAction.REVIEW: "🟠",
        CuratorAction.KEEP: "🟢",
    }

    for a in actions:
        icon = icons.get(a["action"], "⚪")
        lines.append(f"  {icon} [{a['action']:16s}] {a['name']}")
        lines.append(f"     {a['reason']}")

    return "\n".join(lines)


# ── 报告生成 ────────────────────────────────────────────────────────────────

def nudge_report() -> str:
    """
    生成跨会话轻推报告。适合注入到 cross-session context。

    Returns:
        短文本报告，可直接嵌入系统提示。
    """
    skills = scan_skills()
    buckets = assess_staleness(skills)

    total = len(skills)
    fresh = len(buckets["fresh"])
    stale = len(buckets["stale"])
    dormant = len(buckets["dormant"])

    lines = [f"skill_curator: {total}技能 | fresh={fresh} stale={stale} dormant={dormant}"]

    if stale:
        stale_names = [s["name"] for s in buckets["stale"]]
        lines.append(f"stale ({STALE_THRESHOLD_DAYS}+天未触): {', '.join(stale_names)}")

    if dormant:
        dormant_names = [s["name"] for s in buckets["dormant"]]
        lines.append(f"dormant ({DORMANT_THRESHOLD_DAYS}+天未触): {', '.join(dormant_names)}")

    # 补充 registry 中的已沉寂技能
    reg = _get_dormant_registry()
    if reg:
        already = [f"{k}({DORMANT_THRESHOLD_DAYS}+天)" for k in reg]
        if not dormant:  # 避免重复
            lines.append(f"dormant (已沉寂): {', '.join(already)}")

    # 行动建议摘要
    if stale or dormant or reg:
        try:
            data = curator_actions()
            s = data["summary"]
            acts: list[str] = []
            for action, label in [
                (CuratorAction.CAPSULIZE_NOW, "胶囊化"),
                (CuratorAction.PRE_CAPSULIZE, "预警"),
                (CuratorAction.REVIEW, "复核"),
            ]:
                n = s["by_action"].get(action, 0)
                if n:
                    acts.append(f"{label}{n}")
            if acts:
                lines.append(f"action: {' '.join(acts)}")
        except Exception:
            pass

    return "\n".join(lines)


def detailed_report() -> str:
    """生成人类可读的详细报告。"""
    skills = scan_skills()
    buckets = assess_staleness(skills)

    lines = [
        "═" * 50,
        "  Skill Curator 报告",
        "═" * 50,
        f"  总计: {len(skills)} 技能",
        f"  活跃: {len(buckets['fresh'])}",
        f"  静默: {len(buckets['stale'])} (>{STALE_THRESHOLD_DAYS}天)",
        f"  沉睡: {len(buckets['dormant'])} (>{DORMANT_THRESHOLD_DAYS}天)",
        "",
    ]

    if buckets["stale"]:
        lines.append("─" * 50)
        lines.append(f"  ⚠️ 静默技能 (>{STALE_THRESHOLD_DAYS}天未触)")
        lines.append("─" * 50)
        for s in sorted(buckets["stale"], key=lambda x: -(x["days_since"] if isinstance(x["days_since"], int) else 0)):
            lines.append(f"  {s['name']} ({s['category']}): {s['days_since']}天")

    if buckets["dormant"]:
        lines.append("─" * 50)
        lines.append(f"  🔴 沉睡技能 (>{DORMANT_THRESHOLD_DAYS}天未触)")
        lines.append("─" * 50)
        for s in sorted(buckets["dormant"], key=lambda x: -(x["days_since"] if isinstance(x["days_since"], int) else 0)):
            lines.append(f"  {s['name']} ({s['category']}): {s['days_since']}天")

    return "\n".join(lines)


# ── 导出 ────────────────────────────────────────────────────────────────────

__all__ = [
    "touch_skill",
    "scan_skills",
    "scan_all_skills",
    "run_lifecycle_pass",
    "build_lifecycle_report",
    "schedule_skill_curator_lifecycle_pass",
    "assess_staleness",
    "capsulize_and_dormant",
    "revive_skill",
    "curator_actions",
    "curator_actions_report",
    "nudge_report",
    "detailed_report",
    "CuratorAction",
    "SkillStatus",
    "STALE_THRESHOLD_DAYS",
    "DORMANT_THRESHOLD_DAYS",
]
