"""
MimirAether Memory System
记忆系统 - 持久化记忆与上下文管理
"""
import json
import os
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple
import threading
import hashlib
import time

class MemoryEntry:
    """记忆条目"""
    
    def __init__(self, key: str, value: Any, memory_type: str = 'fact',
                 tags: Optional[List[str]] = None, ttl: Optional[int] = None):
        self.key = key
        self.value = value
        self.memory_type = memory_type
        self.tags = tags or []
        self.ttl = ttl
        self.created_at = datetime.now()
        self.updated_at = self.created_at
        self.access_count = 0
        self.last_accessed = self.created_at
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'key': self.key,
            'value': self.value,
            'memory_type': self.memory_type,
            'tags': self.tags,
            'ttl': self.ttl,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'access_count': self.access_count,
            'last_accessed': self.last_accessed.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'MemoryEntry':
        entry = cls(
            key=data['key'],
            value=data['value'],
            memory_type=data.get('memory_type', 'fact'),
            tags=data.get('tags', []),
            ttl=data.get('ttl')
        )
        entry.created_at = datetime.fromisoformat(data['created_at'])
        entry.updated_at = datetime.fromisoformat(data['updated_at'])
        entry.access_count = data.get('access_count', 0)
        entry.last_accessed = datetime.fromisoformat(data.get('last_accessed', data['created_at']))
        return entry


class MemorySystem:
    """记忆系统 - 分层记忆存储"""
    
    # 记忆类型
    TYPE_SHORT = 'short'      # 短期记忆 - 当前会话
    TYPE_WORKING = 'working'   # 工作记忆 - 最近交互
    TYPE_LONG = 'long'        # 长期记忆 - 持久化知识
    TYPE_EPISODIC = 'episodic' # 情景记忆 - 事件记录
    
    # 分层阈值
    WORKING_MAX = 100          # 工作记忆最大条目数
    AGING_INTERVAL = 100       # 老化检查间隔
    
    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            from mimir_constants import get_mimir_home

            db_path = str(get_mimir_home() / "memory.db")
        
        self.db_path = db_path
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        
        self._local = threading.local()
        self._counter = 0
        self._init_db()
    
    def _get_conn(self) -> sqlite3.Connection:
        if not hasattr(self._local, 'conn'):
            self._local.conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self._local.conn.row_factory = sqlite3.Row
        return self._local.conn
    
    def _init_db(self):
        """初始化数据库"""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        # 主记忆表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS memories (
                id TEXT PRIMARY KEY,
                key TEXT UNIQUE NOT NULL,
                value TEXT NOT NULL,
                memory_type TEXT NOT NULL,
                tags TEXT,
                ttl INTEGER,
                importance REAL DEFAULT 0.5,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                access_count INTEGER DEFAULT 0,
                last_accessed TEXT
            )
        """)
        
        # 记忆索引
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_memories_key ON memories(key)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_memories_type ON memories(memory_type)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_memories_importance ON memories(importance)")
        
        # 记忆关系表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS memory_relations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                from_key TEXT NOT NULL,
                to_key TEXT NOT NULL,
                relation_type TEXT,
                strength REAL DEFAULT 0.5,
                created_at TEXT NOT NULL,
                FOREIGN KEY (from_key) REFERENCES memories(key),
                FOREIGN KEY (to_key) REFERENCES memories(key)
            )
        """)
        
        # 记忆历史表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS memory_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                memory_key TEXT NOT NULL,
                operation TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                old_value TEXT,
                new_value TEXT
            )
        """)
        
        conn.commit()
    
    def store(self, key: str, value: Any, memory_type: str = 'fact',
              tags: Optional[List[str]] = None, ttl: Optional[int] = None,
              importance: float = 0.5) -> bool:
        """存储记忆"""
        memory_id = self._generate_id(key)
        now = datetime.now().isoformat()
        
        conn = self._get_conn()
        cursor = conn.cursor()
        
        # 序列化值
        serialized = self._serialize(value)
        
        try:
            cursor.execute("""
                INSERT INTO memories (id, key, value, memory_type, tags, ttl, importance, 
                                     created_at, updated_at, access_count, last_accessed)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?)
            """, (memory_id, key, serialized, memory_type, json.dumps(tags or []),
                  ttl, importance, now, now, now))
            
            conn.commit()
            self._log_history(key, 'create', None, value)
            return True
            
        except sqlite3.IntegrityError:
            # 更新已存在的记忆
            cursor.execute("""
                UPDATE memories SET value=?, memory_type=?, tags=?, ttl=?, importance=?,
                                   updated_at=?, access_count=access_count+1, last_accessed=?
                WHERE key=?
            """, (serialized, memory_type, json.dumps(tags or []), ttl, importance,
                  now, now, key))
            conn.commit()
            self._log_history(key, 'update', None, value)
            return True
    
    def recall(self, key: str, default: Any = None) -> Any:
        """回忆记忆"""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE memories SET access_count = access_count + 1, last_accessed = ?
            WHERE key = ?
        """, (datetime.now().isoformat(), key))
        conn.commit()
        
        cursor.execute('SELECT value FROM memories WHERE key = ?', (key,))
        row = cursor.fetchone()
        
        if row:
            return self._deserialize(row['value'])
        
        return default
    
    def forget(self, key: str) -> bool:
        """遗忘记忆"""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        # 获取旧值用于历史记录
        cursor.execute('SELECT value FROM memories WHERE key = ?', (key,))
        row = cursor.fetchone()
        old_value = self._deserialize(row['value']) if row else None
        
        cursor.execute('DELETE FROM memories WHERE key = ?', (key,))
        conn.commit()
        
        if old_value is not None:
            self._log_history(key, 'delete', old_value, None)
        
        return cursor.rowcount > 0
    
    def search(self, query: Optional[str] = None, tags: Optional[List[str]] = None,
               memory_type: Optional[str] = None, limit: int = 50) -> List[Dict]:
        """搜索记忆"""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        query_sql = 'SELECT * FROM memories WHERE 1=1'
        params = []
        
        if memory_type:
            query_sql += ' AND memory_type = ?'
            params.append(memory_type)
        
        if query:
            query_sql += ' AND (key LIKE ? OR value LIKE ?)'
            search_term = f'%{query}%'
            params.extend([search_term, search_term])
        
        if tags:
            for tag in tags:
                query_sql += ' AND tags LIKE ?'
                params.append(f'%{tag}%')
        
        query_sql += ' ORDER BY importance DESC, access_count DESC LIMIT ?'
        params.append(limit)
        
        cursor.execute(query_sql, params)
        
        results = []
        for row in cursor.fetchall():
            data = dict(row)
            data['tags'] = json.loads(data.get('tags', '[]'))
            data['value'] = self._deserialize(data['value'])
            results.append(data)
        
        return results
    
    def list_keys(self, memory_type: Optional[str] = None, pattern: Optional[str] = None) -> List[str]:
        """列出记忆键"""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        query = 'SELECT key FROM memories WHERE 1=1'
        params = []
        
        if memory_type:
            query += ' AND memory_type = ?'
            params.append(memory_type)
        
        if pattern:
            query += ' AND key LIKE ?'
            params.append(pattern)
        
        query += ' ORDER BY last_accessed DESC'
        
        cursor.execute(query, params)
        return [row['key'] for row in cursor.fetchall()]
    
    def relate(self, from_key: str, to_key: str, relation_type: str = 'related',
               strength: float = 0.5) -> bool:
        """建立记忆关联"""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        now = datetime.now().isoformat()
        
        try:
            cursor.execute("""
                INSERT INTO memory_relations (from_key, to_key, relation_type, strength, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, (from_key, to_key, relation_type, strength, now))
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            cursor.execute("""
                UPDATE memory_relations SET relation_type=?, strength=?
                WHERE from_key=? AND to_key=?
            """, (relation_type, strength, from_key, to_key))
            conn.commit()
            return True
    
    def get_related(self, key: str, relation_type: Optional[str] = None, 
                   limit: int = 10) -> List[Tuple[str, str, float]]:
        """获取关联记忆"""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        query = """
            SELECT to_key, relation_type, strength 
            FROM memory_relations 
            WHERE from_key = ?
        """
        params = [key]
        
        if relation_type:
            query += ' AND relation_type = ?'
            params.append(relation_type)
        
        query += ' ORDER BY strength DESC LIMIT ?'
        params.append(limit)
        
        cursor.execute(query, params)
        return [(row['to_key'], row['relation_type'], row['strength']) for row in cursor.fetchall()]
    
    def get_stats(self) -> Dict[str, Any]:
        """获取记忆统计"""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        # 总记忆数
        cursor.execute('SELECT COUNT(*) as total FROM memories')
        total = cursor.fetchone()['total']
        
        # 按类型统计
        cursor.execute("""
            SELECT memory_type, COUNT(*) as count 
            FROM memories 
            GROUP BY memory_type
        """)
        by_type = {row['memory_type']: row['count'] for row in cursor.fetchall()}
        
        # 高频记忆
        cursor.execute("""
            SELECT key, access_count 
            FROM memories 
            ORDER BY access_count DESC 
            LIMIT 10
        """)
        top_accessed = [{'key': row['key'], 'count': row['access_count']} for row in cursor.fetchall()]
        
        # 最近更新
        cursor.execute("""
            SELECT key, updated_at 
            FROM memories 
            ORDER BY updated_at DESC 
            LIMIT 10
        """)
        recently_updated = [{'key': row['key'], 'updated_at': row['updated_at']} for row in cursor.fetchall()]
        
        # 关联数
        cursor.execute('SELECT COUNT(*) as total FROM memory_relations')
        relations = cursor.fetchone()['total']
        
        return {
            'total_memories': total,
            'by_type': by_type,
            'top_accessed': top_accessed,
            'recently_updated': recently_updated,
            'total_relations': relations
        }
    
    def consolidate(self, target_type: str = 'long') -> int:
        """整合记忆到长期记忆"""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        # 将高频访问的短期记忆转为长期记忆
        threshold = 5  # 访问5次以上
        cursor.execute("""
            UPDATE memories 
            SET memory_type = ?, updated_at = ?
            WHERE memory_type != ? AND access_count >= ?
        """, (target_type, datetime.now().isoformat(), target_type, threshold))
        
        consolidated = cursor.rowcount
        conn.commit()
        
        return consolidated
    
    def cleanup_expired(self) -> int:
        """清理过期记忆"""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        cursor.execute("""
            DELETE FROM memories 
            WHERE ttl IS NOT NULL 
            AND datetime(updated_at, '+' || ttl || ' seconds') < datetime('now')
        """)
        
        deleted = cursor.rowcount
        conn.commit()
        
        return deleted
    
    def export_memories(self, memory_type: Optional[str] = None) -> List[Dict]:
        """导出记忆"""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        query = 'SELECT * FROM memories'
        params = []
        
        if memory_type:
            query += ' WHERE memory_type = ?'
            params.append(memory_type)
        
        cursor.execute(query, params)
        
        results = []
        for row in cursor.fetchall():
            data = dict(row)
            data['tags'] = json.loads(data.get('tags', '[]'))
            data['value'] = self._deserialize(data['value'])
            results.append(data)
        
        return results
    
    def import_memories(self, memories: List[Dict], overwrite: bool = True) -> int:
        """导入记忆"""
        imported = 0
        
        for mem in memories:
            if overwrite:
                self.store(
                    key=mem['key'],
                    value=mem['value'],
                    memory_type=mem.get('memory_type', 'imported'),
                    tags=mem.get('tags', []),
                    importance=mem.get('importance', 0.5)
                )
                imported += 1
            else:
                # 只导入不存在的
                existing = self.recall(mem['key'], None)
                if existing is None:
                    self.store(
                        key=mem['key'],
                        value=mem['value'],
                        memory_type=mem.get('memory_type', 'imported'),
                        tags=mem.get('tags', []),
                        importance=mem.get('importance', 0.5)
                    )
                    imported += 1
        
        return imported
    
    # ============ Helper Methods ============
    
    def _generate_id(self, key: str) -> str:
        return hashlib.md5(key.encode()).hexdigest()[:16]
    
    def _serialize(self, value: Any) -> str:
        if isinstance(value, str):
            return value
        return json.dumps(value, ensure_ascii=False, default=str)
    
    def _deserialize(self, value: str) -> Any:
        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return value
    
    def _log_history(self, key: str, operation: str, old_value: Any, new_value: Any):
        conn = self._get_conn()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO memory_history (memory_key, operation, timestamp, old_value, new_value)
            VALUES (?, ?, ?, ?, ?)
        """, (key, operation, datetime.now().isoformat(),
              self._serialize(old_value) if old_value is not None else None,
              self._serialize(new_value) if new_value is not None else None))
        
        conn.commit()
    
    def close(self):
        """关闭数据库连接"""
        if hasattr(self._local, 'conn'):
            self._local.conn.close()
            del self._local.conn


# 全局实例
_memory_system = None

def get_memory() -> MemorySystem:
    """获取全局记忆系统实例"""
    global _memory_system
    if _memory_system is None:
        _memory_system = MemorySystem()
    return _memory_system


if __name__ == '__main__':
    memory = MemorySystem()
    
    # 存储不同类型的记忆
    memory.store('user_name', 'Alice', memory_type='fact', importance=0.9)
    memory.store('favorite_color', 'blue', memory_type='fact', tags=['preference'])
    memory.store('last_task', 'test memory system', memory_type='working')
    
    # 回忆
    name = memory.recall('user_name')
    print(f"User name: {name}")
    
    # 多次访问增加重要性
    for _ in range(5):
        memory.recall('user_name')
    
    # 建立关联
    memory.relate('user_name', 'favorite_color', 'preference_of', 0.8)
    
    # 搜索
    results = memory.search(tags=['preference'])
    print(f"Search by tag 'preference': {len(results)} results")
    
    # 获取统计
    stats = memory.get_stats()
    print(f"\nMemory stats: {json.dumps(stats, indent=2, default=str)}")
    
    # 获取关联
    related = memory.get_related('user_name')
    print(f"\nRelated to 'user_name': {related}")
    
    # 导出
    exported = memory.export_memories()
    print(f"\nExported {len(exported)} memories")
    
    memory.close()
    print("\nMemory system test completed!")
