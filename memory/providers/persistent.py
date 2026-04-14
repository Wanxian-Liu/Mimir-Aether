"""
MimirAether Persistent Memory Provider

提供持久记忆的存储和检索接口。
"""

import logging
from typing import List, Optional, Dict, Any
from datetime import datetime

from ..memory_manager import MemoryEntry, PersistentMemory

logger = logging.getLogger(__name__)


class PersistentProvider:
    """
    持久记忆提供者
    
    负责跨会话持久化信息的存储和检索。
    """
    
    def __init__(self, memory: PersistentMemory):
        self.memory = memory
        logger.info("PersistentProvider initialized")
    
    def add(self, content: str, metadata: Dict = None) -> MemoryEntry:
        """添加持久记忆"""
        return self.memory.add(content, metadata)
    
    def get_all(self) -> List[MemoryEntry]:
        """获取所有持久记忆"""
        return self.memory.get_all()
    
    def get_recent(self, n: int = 20) -> List[MemoryEntry]:
        """获取最近的n条记忆"""
        return self.memory.get_recent(n)
    
    def get_by_type(self, memory_type: str) -> List[MemoryEntry]:
        """按类型获取记忆"""
        return self.memory.get_by_type(memory_type)
    
    def search(self, keyword: str) -> List[MemoryEntry]:
        """搜索包含关键词的记忆"""
        return self.memory.get_by_keyword(keyword)
    
    def clear(self):
        """清空持久记忆"""
        self.memory.entries = []
        self.memory._save()
        logger.info("Persistent memory cleared")
    
    def count(self) -> int:
        """获取记忆数量"""
        return len(self.memory.entries)
