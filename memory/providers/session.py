"""
MimirAether Session Memory Provider

提供会话记忆的存储和检索接口。
"""

import logging
from typing import List, Optional, Dict, Any
from datetime import datetime

from ..memory_manager import MemoryEntry, SessionMemory

logger = logging.getLogger(__name__)


class SessionProvider:
    """
    会话记忆提供者
    
    负责会话期间的记忆存储和检索。
    """
    
    def __init__(self, memory: SessionMemory):
        self.memory = memory
        logger.info("SessionProvider initialized")
    
    def add(self, content: str, metadata: Dict = None) -> MemoryEntry:
        """添加会话记忆"""
        return self.memory.add(content, metadata)
    
    def get_all(self) -> List[MemoryEntry]:
        """获取所有会话记忆"""
        return self.memory.get_all()
    
    def get_recent(self, n: int = 10) -> List[MemoryEntry]:
        """获取最近的n条记忆"""
        return self.memory.get_recent(n)
    
    def clear(self):
        """清空会话记忆"""
        self.memory.clear()
        logger.info("Session memory cleared")
    
    def count(self) -> int:
        """获取记忆数量"""
        return len(self.memory.entries)
