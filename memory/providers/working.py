"""
MimirAether Working Memory Provider

提供工作记忆的存储和检索接口。
"""

import logging
from typing import List, Optional, Dict, Any
from datetime import datetime

from ..memory_manager import MemoryEntry, WorkingMemory

logger = logging.getLogger(__name__)


class WorkingProvider:
    """
    工作记忆提供者
    
    负责短期重要信息的存储和检索。
    """
    
    def __init__(self, memory: WorkingMemory):
        self.memory = memory
        logger.info("WorkingProvider initialized")
    
    def add(self, content: str, metadata: Dict = None) -> MemoryEntry:
        """添加工的记忆"""
        return self.memory.add(content, metadata)
    
    def get_all(self) -> List[MemoryEntry]:
        """获取所有工作记忆"""
        return self.memory.get_all()
    
    def get_recent(self, n: int = 10) -> List[MemoryEntry]:
        """获取最近的n条记忆"""
        return self.memory.entries[-n:] if len(self.memory.entries) > n else self.memory.entries
    
    def search(self, keyword: str) -> List[MemoryEntry]:
        """搜索包含关键词的记忆"""
        return self.memory.get_by_keyword(keyword)
    
    def clear(self):
        """清空工作记忆"""
        self.memory.clear()
        logger.info("Working memory cleared")
    
    def count(self) -> int:
        """获取记忆数量"""
        return len(self.memory.entries)
