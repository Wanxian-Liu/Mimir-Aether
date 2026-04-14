"""
MimirAether Memory Manager

管理Agent的记忆系统，支持多层级的记忆存储和检索。

层级架构（学习自Hermes）：
- Session Memory：当前对话会话
- Working Memory：短期工作记忆
- Persistent Memory：跨会话持久记忆
- Skill Memory：技能和模式记忆
"""

import json
import logging
from typing import Any, Dict, List, Optional
from datetime import datetime
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class MemoryEntry:
    """记忆条目"""
    id: str
    content: str
    timestamp: str
    memory_type: str  # session, working, persistent, skill
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "content": self.content,
            "timestamp": self.timestamp,
            "memory_type": self.memory_type,
            "metadata": self.metadata
        }


class SessionMemory:
    """会话记忆 - 仅存在于当前会话"""
    
    def __init__(self):
        self.entries: List[MemoryEntry] = []
        self._counter = 0
    
    def add(self, content: str, metadata: Dict = None) -> MemoryEntry:
        self._counter += 1
        entry = MemoryEntry(
            id=f"session_{self._counter}",
            content=content,
            timestamp=datetime.now().isoformat(),
            memory_type="session",
            metadata=metadata or {}
        )
        self.entries.append(entry)
        return entry
    
    def get_all(self) -> List[MemoryEntry]:
        return self.entries
    
    def get_recent(self, n: int = 10) -> List[MemoryEntry]:
        return self.entries[-n:] if len(self.entries) > n else self.entries
    
    def clear(self):
        self.entries = []
        self._counter = 0


class WorkingMemory:
    """工作记忆 - 短期重要信息"""
    
    def __init__(self, max_size: int = 50):
        self.max_size = max_size
        self.entries: List[MemoryEntry] = []
        self._counter = 0
    
    def add(self, content: str, metadata: Dict = None) -> MemoryEntry:
        self._counter += 1
        entry = MemoryEntry(
            id=f"working_{self._counter}",
            content=content,
            timestamp=datetime.now().isoformat(),
            memory_type="working",
            metadata=metadata or {}
        )
        self.entries.append(entry)
        
        # 保持大小限制
        if len(self.entries) > self.max_size:
            self.entries.pop(0)
        
        return entry
    
    def get_all(self) -> List[MemoryEntry]:
        return self.entries
    
    def get_by_keyword(self, keyword: str) -> List[MemoryEntry]:
        return [e for e in self.entries if keyword.lower() in e.content.lower()]
    
    def clear(self):
        self.entries = []


class PersistentMemory:
    """持久记忆 - 跨会话存储"""
    
    def __init__(self, storage_path: str = None):
        import os
        if storage_path is None:
            storage_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                "memory", "persistent.json"
            )
        self.storage_path = storage_path
        self.entries: List[MemoryEntry] = []
        self._counter = 0
        self._load()
    
    def _load(self):
        """从磁盘加载记忆"""
        import os
        if os.path.exists(self.storage_path):
            try:
                with open(self.storage_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.entries = [
                        MemoryEntry(**item) for item in data.get("entries", [])
                    ]
                    self._counter = data.get("counter", 0)
                logger.info(f"Loaded {len(self.entries)} persistent memories")
            except Exception as e:
                logger.error(f"Failed to load persistent memory: {e}")
    
    def _save(self):
        """保存记忆到磁盘"""
        import os
        os.makedirs(os.path.dirname(self.storage_path), exist_ok=True)
        try:
            with open(self.storage_path, "w", encoding="utf-8") as f:
                json.dump({
                    "counter": self._counter,
                    "entries": [e.to_dict() for e in self.entries]
                }, f, ensure_ascii=False, indent=2)
            # 设置文件权限为600（仅所有者读写）
            os.chmod(self.storage_path, 0o600)
        except Exception as e:
            logger.error(f"Failed to save persistent memory: {e}")
    
    def add(self, content: str, metadata: Dict = None) -> MemoryEntry:
        self._counter += 1
        entry = MemoryEntry(
            id=f"persistent_{self._counter}",
            content=content,
            timestamp=datetime.now().isoformat(),
            memory_type="persistent",
            metadata=metadata or {}
        )
        self.entries.append(entry)
        self._save()
        return entry
    
    def get_all(self) -> List[MemoryEntry]:
        return self.entries
    
    def get_recent(self, n: int = 20) -> List[MemoryEntry]:
        return self.entries[-n:] if len(self.entries) > n else self.entries
    
    def get_by_type(self, memory_type: str) -> List[MemoryEntry]:
        return [e for e in self.entries if e.memory_type == memory_type]
    
    def get_by_keyword(self, keyword: str) -> List[MemoryEntry]:
        return [e for e in self.entries if keyword.lower() in e.content.lower()]
    
    def clear(self):
        self.entries = []
        self._save()


class SkillMemory:
    """技能记忆 - 存储学习到的模式和技能"""
    
    def __init__(self, storage_path: str = None):
        import os
        if storage_path is None:
            storage_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                "memory", "skills.json"
            )
        self.storage_path = storage_path
        self.skills: Dict[str, Dict] = {}
        self._load()
    
    def _load(self):
        """从磁盘加载技能"""
        import os
        if os.path.exists(self.storage_path):
            try:
                with open(self.storage_path, "r", encoding="utf-8") as f:
                    self.skills = json.load(f)
                logger.info(f"Loaded {len(self.skills)} skills")
            except Exception as e:
                logger.error(f"Failed to load skills: {e}")
    
    def _save(self):
        """保存技能到磁盘"""
        import os
        os.makedirs(os.path.dirname(self.storage_path), exist_ok=True)
        try:
            with open(self.storage_path, "w", encoding="utf-8") as f:
                json.dump(self.skills, f, ensure_ascii=False, indent=2)
            # 设置文件权限为600（仅所有者读写）
            os.chmod(self.storage_path, 0o600)
        except Exception as e:
            logger.error(f"Failed to save skills: {e}")
    
    def add_skill(self, name: str, skill_data: Dict) -> bool:
        """添加技能"""
        self.skills[name] = {
            "name": name,
            "data": skill_data,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        }
        self._save()
        return True
    
    def get_skill(self, name: str) -> Optional[Dict]:
        return self.skills.get(name)
    
    def list_skills(self) -> List[str]:
        return list(self.skills.keys())
    
    def remove_skill(self, name: str) -> bool:
        if name in self.skills:
            del self.skills[name]
            self._save()
            return True
        return False


class MemoryManager:
    """
    记忆管理器 - 统一管理多层记忆
    
    提供统一的接口访问所有层级的记忆。
    """
    
    def __init__(self, storage_dir: str = None):
        import os
        if storage_dir is None:
            storage_dir = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                "memory"
            )
        
        self.session = SessionMemory()
        self.working = WorkingMemory()
        self.persistent = PersistentMemory(
            os.path.join(storage_dir, "persistent.json")
        )
        self.skills = SkillMemory(
            os.path.join(storage_dir, "skills.json")
        )
        
        logger.info("MemoryManager initialized")
    
    def add_memory(self, content: str, memory_type: str = "session", 
                   metadata: Dict = None) -> Optional[MemoryEntry]:
        """
        添加记忆
        
        Args:
            content: 记忆内容
            memory_type: 记忆类型 (session/working/persistent)
            metadata: 元数据
            
        Returns:
            添加的记忆条目
        """
        if memory_type == "session":
            return self.session.add(content, metadata)
        elif memory_type == "working":
            return self.working.add(content, metadata)
        elif memory_type == "persistent":
            return self.persistent.add(content, metadata)
        else:
            logger.warning(f"Unknown memory type: {memory_type}")
            return None
    
    def get_all_context(self) -> List[Dict[str, Any]]:
        """
        获取所有层级的上下文记忆
        
        用于在调用模型时提供背景信息。
        安全措施：限制长度，防止prompt注入。
        """
        context = []
        MAX_CONTENT_LENGTH = 2000  # 单条记忆最大长度
        MAX_TOTAL_LENGTH = 8000  # 记忆上下文总长度上限
        
        # Prompt injection 防护模式
        INJECTION_PATTERNS = [
            r'(?i)(ignore\s+previous\s+instructions)',
            r'(?i)(ignore\s+all\s+previous\s+commands)',
            r'(?i)(disregard\s+your\s+instructions)',
            r'(?i)(you\s+are\s+now\s+)',
            r'(?i)(system\s+prompt\s+leak)',
            r'(?i)(reveal\s+your\s+system\s+prompt)',
            r'\{\{.*\}\}',  # 模板注入
            r'\$\{[^}]+\}',  # 变量注入
            r'<script[^>]*>',  # XSS尝试
            r'<!--.*-->',  # HTML注释注入
        ]
        
        import re
        INJECTION_REGEX = re.compile('|'.join(INJECTION_PATTERNS), re.IGNORECASE)
        
        def sanitize_content(content: str, label: str) -> str:
            """清理内容，防止prompt注入"""
            if not content:
                return f"[{label}] empty"
            # 移除prompt注入模式
            content = INJECTION_REGEX.sub('[REDACTED]', content)
            # 截断过长内容
            if len(content) > MAX_CONTENT_LENGTH:
                content = content[:MAX_CONTENT_LENGTH] + "..."
            return f"[{label}] {content}"
        
        # 计算总长度
        total_length = 0
        
        # 工作记忆（最重要，优先添加）
        for entry in self.working.get_all():
            if total_length >= MAX_TOTAL_LENGTH:
                break
            safe_content = sanitize_content(entry.content, "Working Memory")
            context.append({
                "role": "system",
                "content": safe_content
            })
            total_length += len(safe_content)
        
        # 持久记忆（近期）
        for entry in self.persistent.get_recent(5):
            if total_length >= MAX_TOTAL_LENGTH:
                break
            safe_content = sanitize_content(entry.content, "Persistent Memory")
            context.append({
                "role": "system",
                "content": safe_content
            })
            total_length += len(safe_content)
        
        return context
    
    def search(self, keyword: str) -> List[Dict[str, Any]]:
        """
        搜索所有记忆中的关键词
        
        Returns:
            匹配的记忆列表
        """
        results = []
        
        # 搜索工作记忆
        for entry in self.working.get_by_keyword(keyword):
            results.append({
                "memory_type": "working",
                "entry": entry.to_dict()
            })
        
        # 搜索持久记忆
        for entry in self.persistent.get_by_keyword(keyword):
            results.append({
                "memory_type": "persistent", 
                "entry": entry.to_dict()
            })
        
        return results
    
    def reset_session(self):
        """重置会话记忆（保留持久记忆）"""
        self.session.clear()
        logger.info("Session memory cleared")
    
    def reset_all(self):
        """重置所有记忆"""
        self.session.clear()
        self.working.clear()
        self.persistent.entries = []
        self.persistent._save()
        logger.info("All memory cleared")
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取记忆统计信息"""
        return {
            "session_count": len(self.session.entries),
            "working_count": len(self.working.entries),
            "persistent_count": len(self.persistent.entries),
            "skill_count": len(self.skills.list_skills())
        }


# 导出的类和函数
__all__ = [
    "MemoryManager",
    "SessionMemory",
    "WorkingMemory", 
    "PersistentMemory",
    "SkillMemory",
    "MemoryEntry",
]
