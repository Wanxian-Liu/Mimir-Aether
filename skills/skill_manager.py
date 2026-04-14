"""
MimirAether Skill Manager

自进化Skill管理系统，支持动态加载、注册和自进化。

核心功能：
- Skill注册与发现
- 动态Skill加载
- Skill执行与结果存储
- 自进化机制（基于执行结果学习）
"""

import asyncio
import json
import logging
import os
import importlib
import inspect
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

logger = logging.getLogger(__name__)


class SkillStatus(Enum):
    """Skill状态"""
    INACTIVE = "inactive"      # 未激活
    ACTIVE = "active"        # 已激活
    LEARNING = "learning"      # 学习中
    EVOLVED = "evolved"       # 已进化


@dataclass
class SkillMetadata:
    """Skill元数据"""
    name: str
    description: str
    version: str
    category: str
    author: str = "unknown"
    tags: List[str] = field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""
    usage_count: int = 0
    success_count: int = 0
    success_rate: float = 0.0
    
    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "category": self.category,
            "author": self.author,
            "tags": self.tags,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "usage_count": self.usage_count,
            "success_count": self.success_count,
            "success_rate": self.success_rate
        }


@dataclass
class Skill:
    """Skill定义"""
    metadata: SkillMetadata
    handler: Callable
    schema: Dict[str, Any]
    enabled: bool = True
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "metadata": self.metadata.to_dict(),
            "schema": self.schema,
            "enabled": self.enabled
        }


class SkillManager:
    """
    Skill管理器
    
    管理所有Skill的注册、加载、执行和自进化。
    """
    
    def __init__(self, storage_dir: str = None):
        import os
        if storage_dir is None:
            storage_dir = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                "skills", "data"
            )
        self.storage_dir = storage_dir
        self.skills: Dict[str, Skill] = {}
        self._skill_handlers: Dict[str, Any] = {}
        
        os.makedirs(self.storage_dir, exist_ok=True)
        self._load_skills_metadata()
        
        logger.info(f"SkillManager initialized with {len(self.skills)} skills")
    
    def _load_skills_metadata(self):
        """加载Skill元数据"""
        metadata_file = os.path.join(self.storage_dir, "skills_metadata.json")
        if os.path.exists(metadata_file):
            try:
                with open(metadata_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for name, meta_dict in data.items():
                        self.skills[name] = Skill(
                            metadata=SkillMetadata(**meta_dict),
                            handler=None,
                            schema={},
                            enabled=False
                        )
                logger.info(f"Loaded metadata for {len(self.skills)} skills")
            except Exception as e:
                logger.error(f"Failed to load skills metadata: {e}")
    
    def _save_skills_metadata(self):
        """保存Skill元数据"""
        metadata_file = os.path.join(self.storage_dir, "skills_metadata.json")
        try:
            data = {
                name: skill.metadata.to_dict()
                for name, skill in self.skills.items()
            }
            with open(metadata_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Failed to save skills metadata: {e}")
    
    def register_skill(
        self,
        name: str,
        description: str,
        handler: Callable,
        schema: Dict[str, Any],
        category: str = "general",
        tags: List[str] = None,
        version: str = "1.0.0",
        author: str = "unknown"
    ) -> bool:
        """
        注册新Skill
        
        Args:
            name: Skill名称
            description: Skill描述
            handler: Skill处理函数
            schema: Skill参数schema
            category: Skill分类
            tags: 标签列表
            version: 版本号
            author: 作者
            
        Returns:
            是否注册成功
        """
        if name in self.skills:
            logger.warning(f"Skill {name} already registered, updating...")
        
        metadata = SkillMetadata(
            name=name,
            description=description,
            version=version,
            category=category,
            author=author,
            tags=tags or []
        )
        
        self.skills[name] = Skill(
            metadata=metadata,
            handler=handler,
            schema=schema,
            enabled=True
        )
        self._skill_handlers[name] = handler
        self._save_skills_metadata()
        
        logger.info(f"Registered skill: {name}")
        return True
    
    async def execute_skill(self, name: str, **kwargs) -> Any:
        """
        执行Skill
        
        Args:
            name: Skill名称
            **kwargs: Skill参数
            
        Returns:
            Skill执行结果
        """
        if name not in self.skills:
            raise ValueError(f"Skill not found: {name}")
        
        skill = self.skills[name]
        if not skill.enabled:
            raise ValueError(f"Skill is disabled: {name}")
        
        if skill.handler is None:
            raise ValueError(f"Skill handler not loaded: {name}")
        
        # 更新使用统计
        skill.metadata.usage_count += 1
        skill.metadata.updated_at = datetime.now().isoformat()
        
        try:
            # 执行handler
            if asyncio.iscoroutinefunction(skill.handler):
                result = await skill.handler(**kwargs)
            else:
                result = skill.handler(**kwargs)
            
            # 更新成功统计
            skill.metadata.success_count += 1
            skill.metadata.success_rate = (
                skill.metadata.success_count / skill.metadata.usage_count
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Skill execution failed: {name}, error: {e}")
            raise
        finally:
            self._save_skills_metadata()
    
    def get_skill(self, name: str) -> Optional[Skill]:
        """获取Skill"""
        return self.skills.get(name)
    
    def list_skills(
        self,
        category: str = None,
        enabled_only: bool = True
    ) -> List[Skill]:
        """
        列出Skills
        
        Args:
            category: 按分类过滤
            enabled_only: 只返回已启用的
            
        Returns:
            Skill列表
        """
        skills = self.skills.values()
        
        if category:
            skills = [s for s in skills if s.metadata.category == category]
        
        if enabled_only:
            skills = [s for s in skills if s.enabled]
        
        return list(skills)
    
    def enable_skill(self, name: str) -> bool:
        """启用Skill"""
        if name not in self.skills:
            return False
        self.skills[name].enabled = True
        self._save_skills_metadata()
        return True
    
    def disable_skill(self, name: str) -> bool:
        """禁用Skill"""
        if name not in self.skills:
            return False
        self.skills[name].enabled = False
        self._save_skills_metadata()
        return True
    
    def remove_skill(self, name: str) -> bool:
        """移除Skill"""
        if name not in self.skills:
            return False
        del self.skills[name]
        if name in self._skill_handlers:
            del self._skill_handlers[name]
        self._save_skills_metadata()
        return True
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        total = len(self.skills)
        enabled = sum(1 for s in self.skills.values() if s.enabled)
        total_usage = sum(s.metadata.usage_count for s in self.skills.values())
        total_success = sum(s.metadata.success_count for s in self.skills.values())
        
        return {
            "total_skills": total,
            "enabled_skills": enabled,
            "disabled_skills": total - enabled,
            "total_usage": total_usage,
            "total_success": total_success,
            "overall_success_rate": (
                total_success / total_usage if total_usage > 0 else 0
            )
        }
    
    async def evolve_skill(self, name: str, new_handler: Callable) -> bool:
        """
        进化Skill
        
        基于执行结果学习，更新handler。
        
        Args:
            name: Skill名称
            new_handler: 新的处理函数
            
        Returns:
            是否进化成功
        """
        if name not in self.skills:
            return False
        
        skill = self.skills[name]
        old_handler = skill.handler
        
        skill.handler = new_handler
        skill.metadata.status = SkillStatus.EVOLVED
        skill.metadata.updated_at = datetime.now().isoformat()
        
        self._skill_handlers[name] = new_handler
        self._save_skills_metadata()
        
        logger.info(f"Evolved skill: {name}")
        return True


# 导出的类和函数
__all__ = [
    "SkillManager",
    "Skill",
    "SkillMetadata",
    "SkillStatus",
]
