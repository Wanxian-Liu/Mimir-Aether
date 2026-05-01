"""
MimirAether Skill Memory Provider

提供技能和模式记忆的存储和检索接口。
"""

import logging
from typing import List, Optional, Dict, Any
from datetime import datetime

from ..memory_manager import SkillMemory

logger = logging.getLogger(__name__)


class SkillProvider:
    """
    技能记忆提供者
    
    负责存储和检索学习到的技能和模式。
    """
    
    def __init__(self, memory: SkillMemory):
        self.memory = memory
        logger.info("SkillProvider initialized")
    
    def add_skill(self, name: str, skill_data: Dict) -> bool:
        """添加技能"""
        return self.memory.add_skill(name, skill_data)
    
    def get_skill(self, name: str) -> Optional[Dict]:
        """获取指定技能"""
        return self.memory.get_skill(name)
    
    def list_skills(self) -> List[str]:
        """列出所有技能"""
        return self.memory.list_skills()
    
    def remove_skill(self, name: str) -> bool:
        """移除技能"""
        return self.memory.remove_skill(name)
    
    def count(self) -> int:
        """获取技能数量"""
        return len(self.memory.list_skills())
    
    def has_skill(self, name: str) -> bool:
        """检查技能是否存在"""
        return name in self.memory.list_skills()
