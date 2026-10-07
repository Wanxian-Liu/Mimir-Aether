#!/usr/bin/env python3
"""
MimirAether Skill同步

同步内置Skills到项目目录，支持：
- 检查更新
- 增量同步
- 版本控制
"""

import hashlib
import json
import logging
import os
import shutil
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

# =============================================================================
# 路径配置
# =============================================================================

def get_skills_source_dir() -> Path:
    """Skills源目录（MimirAether内置）"""
    return Path(__file__).parent.parent / "skills"

def get_skills_target_dir() -> Path:
    """Skills 目标目录（与运行时 ``get_skills_dir()`` 一致）。"""
    from mimir_constants import get_skills_dir

    return get_skills_dir()

def get_sync_cache_path() -> Path:
    """同步缓存路径"""
    from mimir_constants import get_mimir_data_dir

    cache_dir = get_mimir_data_dir() / "cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir / "skills_sync.json"

#: 部署侧只读政策文件名（放**目标根目录**：它不在任何 skill 目录内，
#: 既不会被 copytree 抹掉，也不污染「部署侧内容摘要」这一漂移判据）
READONLY_README = "README-只读.md"

#: 漂移告警前缀（用转义序列写，避免源码里出现变体选择符）
DRIFT_WARN_PREFIX = "\u26a0\ufe0f 部署侧漂移:"

READONLY_TEXT = """# 本目录只读（由同步覆盖）

**本目录由 `tools/skills_sync.py` 从源侧整目录替换，任何本地改动都会在下次同步时被覆盖。**

- 唯一真源（源侧）：`~/src/MimirAether/skills/<skill>/`
- 改动一律回源侧；**不要在本目录（部署侧）做本地修复** —— 会被静默覆盖。

同步器在覆盖每个 skill 前会比对「部署侧当前内容摘要」与「上次同步时记下的部署侧摘要」，
不等即判定**部署侧被本地改过**，此时它会：

1. 先把被改过的目录备份到 `<sync_cache_dir>/drift-backup/<skill>-<摘要前8>/`
2. 打一行 `\u26a0\ufe0f 部署侧漂移: <skill>（已备份至 …）`
3. **仍按源侧内容覆盖**（源侧是唯一权威；不做双向合并、不阻塞同步）
"""

# =============================================================================
# Skill同步
# =============================================================================

class SkillSync:
    """
    Skill同步器
    
    功能：
    - 列出内置Skills
    - 检查Skills状态
    - 同步到用户目录
    """
    
    def __init__(self, source_dir: Optional[Path] = None, target_dir: Optional[Path] = None):
        self.source_dir = source_dir or get_skills_source_dir()
        self.target_dir = target_dir or get_skills_target_dir()
        self.cache_path = get_sync_cache_path()
    
    def list_skills(self) -> List[str]:
        """列出内置Skills"""
        if not self.source_dir.exists():
            return []
        
        skills = []
        for item in self.source_dir.iterdir():
            if item.is_dir() and not item.name.startswith('_'):
                skills.append(item.name)
        return sorted(skills)
    
    def get_skill_info(self, skill_name: str) -> Dict:
        """获取Skill信息"""
        skill_dir = self.source_dir / skill_name
        if not skill_dir.exists():
            return {"exists": False}
        
        # 检查SKILL.md
        skill_md = skill_dir / "SKILL.md"
        has_skills_md = skill_md.exists()
        
        # 获取大小
        total_size = sum(
            f.stat().st_size 
            for f in skill_dir.rglob("*") 
            if f.is_file()
        )
        
        return {
            "name": skill_name,
            "exists": True,
            "has_skills_md": has_skills_md,
            "path": str(skill_dir),
            "size": total_size,
        }
    
    def _dir_digest(self, d: Path) -> str:
        """任意目录的内容摘要（相对路径 + 每文件 sha256 汇总）。

        与 ``_skill_digest`` 同一把尺，只是可作用于**任意**目录 —— 用来给
        部署侧目录算摘要，从而判「部署侧是否被人改过」（Q9 漂移闸）。
        """
        if not d.exists():
            return ""
        h = hashlib.sha256()
        for f in sorted(p for p in d.rglob("*") if p.is_file()):
            rel = str(f.relative_to(d)).replace(os.sep, "/")
            h.update(rel.encode("utf-8"))
            h.update(b"\x00")
            h.update(hashlib.sha256(f.read_bytes()).digest())
            h.update(b"\x00")
        return h.hexdigest()

    def _drift_backup_root(self) -> Path:
        """漂移备份根目录（与同步缓存同域，便于一起清理 / 审计）。"""
        return self.cache_path.parent / "drift-backup"

    def _detect_target_drift(self, skill_name: str) -> Optional[Path]:
        """覆盖前漂移闸：部署侧当前内容 vs **上次同步缓存里的摘要**。

        判据（Q9 治本）：缓存里除源侧摘要外，另记「上次同步后的部署侧摘要」。
        部署侧现状与基线不等 即 有人改过部署侧 则 先备份 + 出声，
        **仍按源侧覆盖**（源侧是唯一权威；不阻塞、不双向合并）。

        返回备份目录（有漂移时）；无漂移 / 无基线返回 ``None``。
        旧缓存（无部署侧基线）不误报 —— 首轮只建基线（防假阳性）。
        """
        target = self.target_dir / skill_name
        if not target.exists():
            return None
        recorded = self._cached_target_digests().get(skill_name)
        if not recorded:
            return None                      # 无基线：不误报（旧缓存首轮）
        current = self._dir_digest(target)
        if current == recorded:
            return None                      # 部署侧未被改过：零出声零备份

        backup = self._drift_backup_root() / ("%s-%s" % (skill_name, current[:8]))
        if backup.exists():
            shutil.rmtree(backup)                   # 同摘要重跑：以本次部署侧现状为准
        backup.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(target, backup)
        logger.warning(DRIFT_WARN_PREFIX + " %s（已备份至 %s）", skill_name, backup)
        return backup

    def sync_skill(self, skill_name: str) -> bool:
        """同步单个Skill到目标目录（覆盖前过漂移闸）"""
        source = self.source_dir / skill_name
        if not source.exists():
            return False
        
        target = self.target_dir / skill_name
        
        # 创建目标目录
        self.target_dir.mkdir(parents=True, exist_ok=True)
        
        # Q9 覆盖前漂移闸：部署侧被本地改过 则 先备份 + 出声（源侧仍是权威，不阻塞）
        self._detect_target_drift(skill_name)
        
        # 复制文件
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(source, target)
        
        # 更新缓存
        self._update_cache(skill_name)
        
        return True

    def sync_all(self, only: Optional[List[str]] = None) -> Dict[str, bool]:
        """同步Skills。

        ``only`` 给定时只同步这些（= ``get_sync_status()["pending_skills"]``）——
        这是「未变的不动」的消费端；默认 ``None`` 保持原语义（全量），
        既有调用方不受影响（向后兼容 + 可逆）。
        """
        results = {}
        skill_names = self.list_skills() if only is None else list(only)
        for skill_name in skill_names:
            results[skill_name] = self.sync_skill(skill_name)
        return results
    
    def _cached_digests(self) -> Dict[str, str]:
        """读缓存中的「skill -> 源侧内容摘要」表。

        向后兼容：旧形态是 ``{"synced": [name, ...]}``（只记名字、无摘要）。
        历史名单既可能含已删技能、也可能缺新增技能，因此**不可**与源侧存量
        相减——旧判据 ``len(all_skills) - len(synced)`` 即此错，实测 19-29=-10。
        这里把旧形态读成空表 ⇒ 本轮全部计为待同步一次，同步后自愈。
        """
        import json

        if not self.cache_path.exists():
            return {}
        with open(self.cache_path) as f:
            data = json.load(f)
        raw = data.get("synced", {})
        return dict(raw) if isinstance(raw, dict) else {}

    def _cached_target_digests(self) -> Dict[str, str]:
        """读缓存中的「skill -> 上次同步后的部署侧内容摘要」表（Q9 漂移基线）。

        与 ``_cached_digests``（源侧摘要）分开存：两者语义不同 ——
        源侧摘要答「源变了没」，部署侧摘要答「部署侧被人改过没」。
        缺该表（旧缓存）⇒ 无基线 ⇒ 不判漂移（首轮只建基线，防假阳性）。
        """
        if not self.cache_path.exists():
            return {}
        with open(self.cache_path) as f:
            data = json.load(f)
        raw = data.get("target", {})
        return dict(raw) if isinstance(raw, dict) else {}

    def _skill_digest(self, skill_name: str) -> str:
        """源侧 skill 目录的内容摘要（相对路径 + 每文件 sha256 汇总）。

        判据用**内容摘要**而非 mtime：mtime 在 git checkout / cp / 部署侧改动下
        会漂移（假阳性重拷 = 本次事故同类）。实测全量 436 文件 / 6.8MB 算 sha256
        仅 0.040s（stat-only 0.027s），不值得为省 13ms 换正确性。
        """
        import hashlib

        skill_dir = self.source_dir / skill_name
        if not skill_dir.exists():
            return ""
        h = hashlib.sha256()
        for f in sorted(p for p in skill_dir.rglob("*") if p.is_file()):
            rel = str(f.relative_to(skill_dir)).replace(os.sep, "/")
            h.update(rel.encode("utf-8"))
            h.update(b"\x00")
            h.update(hashlib.sha256(f.read_bytes()).digest())
            h.update(b"\x00")
        return h.hexdigest()

    def _needs_sync(self, skill_name: str, cached: Dict[str, str]) -> bool:
        """单个 skill 是否需要同步（三条充分条件，任一成立即待同步）"""
        digest = cached.get(skill_name)
        if digest is None:
            return True                      # 缓存无该条（含旧形态升级后首轮）
        if not (self.target_dir / skill_name).exists():
            return True                      # 目标缺失（被删 / 从未拷贝）
        return self._skill_digest(skill_name) != digest   # 源侧内容真变了

    def get_sync_status(self) -> Dict:
        """获取同步状态。

        口径（2026-10-07 修）：``pending`` = 待同步 skill 数 =
        「源侧内容摘要 ≠ 缓存摘要」+「目标缺失」+「缓存无记录」。
        旧口径把「源目录当前存量」与「缓存历史累积名单」两个不同语义的集合
        相减 ⇒ 读数可为负（实测 -10）⇒ ``pending == 0`` 恒 False ⇒ 闸从不生效。
        """
        cached = self._cached_digests()
        all_skills = self.list_skills()
        pending_skills = [n for n in all_skills if self._needs_sync(n, cached)]

        return {
            "total": len(all_skills),
            "synced": len(all_skills) - len(pending_skills),
            "pending": len(pending_skills),
            "pending_skills": pending_skills,
            "cached_total": len(cached),
            "skills": all_skills,
        }

    def ensure_readonly_policy(self) -> Path:
        """在部署侧**目标根目录**写只读政策 ``README-只读.md``（幂等）。

        位置取目标根而非每个 skill 目录：本闸判据是「部署侧内容 vs 上次同步
        基线」，根目录文件不在任何 skill 目录内 ⇒ 既不会被 copytree 抹掉，
        也不会污染漂移判据（避免每轮假漂移）。
        """
        self.target_dir.mkdir(parents=True, exist_ok=True)
        notice = self.target_dir / READONLY_README
        if not notice.exists() or notice.read_text(encoding="utf-8") != READONLY_TEXT:
            notice.write_text(READONLY_TEXT, encoding="utf-8")
        return notice

    def _update_cache(self, skill_name: str):
        """更新同步缓存（记源侧内容摘要；旧 list 形态在此升级为 dict）"""
        import json

        data = {"synced": {}}
        if self.cache_path.exists():
            with open(self.cache_path) as f:
                data = json.load(f)
        if not isinstance(data.get("synced"), dict):
            data["synced"] = {}

        data["synced"][skill_name] = self._skill_digest(skill_name)

        # Q9 漂移基线：记下本次同步**之后**部署侧的内容摘要 —— 下次覆盖前
        # 拿它与部署侧现状比对，不等即「有人改过部署侧」⇒ 备份 + 出声。
        target_digest = self._dir_digest(self.target_dir / skill_name)
        if target_digest:
            if not isinstance(data.get("target"), dict):
                data["target"] = {}
            data["target"][skill_name] = target_digest

        with open(self.cache_path, 'w') as f:
            json.dump(data, f)

# =============================================================================
# 闸门判决落痕（可观测性）
# =============================================================================

def _record_sync_decision(cache_path: Path, status: Dict) -> None:
    """把本次闸门判决写入缓存文件（``last_decision``）。

    目的：本闸 2026-10-07 前**恒不生效且零痕迹** —— 事故只能靠外部复算
    （19-29=-10）才发现。「跳过」与「重拷」必须在盘上可区分，否则同类故障
    仍不可见。副作用仅多一个键，删除本函数与调用点即可完全回滚。
    """
    import json

    data = {"synced": {}}
    if cache_path.exists():
        with open(cache_path) as f:
            data = json.load(f)
    if not isinstance(data.get("synced"), dict):
        data["synced"] = {}
    data["last_decision"] = {
        "pending": status["pending"],
        "total": status["total"],
        "pending_skills": status.get("pending_skills", []),
        "action": "skip" if status["pending"] == 0 else "sync",
    }
    with open(cache_path, "w") as f:
        json.dump(data, f)


# =============================================================================
# CLI接口
# =============================================================================

def sync_skills(quiet: bool = False) -> bool:
    """
    同步所有Skills
    
    Args:
        quiet: 是否静默模式
        
    Returns:
        是否成功
    """
    sync = SkillSync()
    
    # 获取状态
    # 只读政策落文（Q9）：部署侧根目录一份，每次同步保证它在（幂等）
    sync.ensure_readonly_policy()

    status = sync.get_sync_status()
    
    if not quiet:
        print(f"Skills同步状态:")
        print(f"  总数: {status['total']}")
        print(f"  已同步: {status['synced']}")
        print(f"  待同步: {status['pending']}")
    
    _record_sync_decision(sync.cache_path, status)

    if status['pending'] == 0:
        if not quiet:
            print("  所有Skills已是最新")
        # 可观测性(§5.5 不可裁剪): 本闸 2026-10-07 前恒不生效且全程零日志,
        # 事故只能靠外部复算发现 -- 留一行 INFO 让「跳过」与「重拷」可区分。
        logger.info("skills_sync: no change, skip (total=%d synced=%d)",
                    status['total'], status['synced'])
        return True

    logger.info("skills_sync: syncing %d/%d: %s", status["pending"],
                status['total'], ','.join(status.get('pending_skills', [])))
    
    # 执行同步 —— 只同步判据认定的待同步项（未变的不动）
    results = sync.sync_all(only=status["pending_skills"])
    
    if not quiet:
        success = sum(1 for v in results.values() if v)
        print(f"  已同步 {success}/{len(results)} 个Skills")
    
    return True


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="MimirAether Skill同步")
    parser.add_argument("--quiet", action="store_true", help="静默模式")
    parser.add_argument("--list", action="store_true", help="列出Skills")
    parser.add_argument("--sync", type=str, help="同步指定Skill")
    
    args = parser.parse_args()
    
    sync = SkillSync()
    
    if args.list:
        print("内置Skills:")
        for skill in sync.list_skills():
            info = sync.get_skill_info(skill)
            print(f"  - {skill}")
    elif args.sync:
        success = sync.sync_skill(args.sync)
        print(f"同步 {args.sync}: {'成功' if success else '失败'}")
    else:
        sync_skills()
