#!/usr/bin/env python3
"""
MimirAether Skill同步

同步内置Skills到项目目录，支持：
- 检查更新
- 增量同步
- 版本控制
"""

import os
import shutil
from pathlib import Path
from typing import Dict, List, Optional

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
    
    def sync_skill(self, skill_name: str) -> bool:
        """同步单个Skill到目标目录"""
        source = self.source_dir / skill_name
        if not source.exists():
            return False
        
        target = self.target_dir / skill_name
        
        # 创建目标目录
        self.target_dir.mkdir(parents=True, exist_ok=True)
        
        # 复制文件
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(source, target)
        
        # 更新缓存
        self._update_cache(skill_name)
        
        return True
    
    def sync_all(self) -> Dict[str, bool]:
        """同步所有Skills"""
        results = {}
        for skill_name in self.list_skills():
            results[skill_name] = self.sync_skill(skill_name)
        return results
    
    def get_sync_status(self) -> Dict:
        """获取同步状态"""
        synced = set()
        if self.cache_path.exists():
            import json
            with open(self.cache_path) as f:
                data = json.load(f)
                synced = set(data.get("synced", []))
        
        all_skills = self.list_skills()
        
        return {
            "total": len(all_skills),
            "synced": len(synced),
            "pending": len(all_skills) - len(synced),
            "skills": all_skills,
        }
    
    def _update_cache(self, skill_name: str):
        """更新同步缓存"""
        import json
        
        data = {"synced": []}
        if self.cache_path.exists():
            with open(self.cache_path) as f:
                data = json.load(f)
        
        if skill_name not in data["synced"]:
            data["synced"].append(skill_name)
        
        with open(self.cache_path, 'w') as f:
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
    status = sync.get_sync_status()
    
    if not quiet:
        print(f"Skills同步状态:")
        print(f"  总数: {status['total']}")
        print(f"  已同步: {status['synced']}")
        print(f"  待同步: {status['pending']}")
    
    if status['pending'] == 0:
        if not quiet:
            print("  所有Skills已是最新")
        return True
    
    # 执行同步
    results = sync.sync_all()
    
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
