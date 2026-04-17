#!/usr/bin/env python3
"""
MimirAether 会话管理器

基于SQLite的会话持久化，支持：
- 会话创建/恢复
- 消息历史
- 自动保存
"""

import json
import sqlite3
import time
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Any
from dataclasses import dataclass

# =============================================================================
# 路径配置
# =============================================================================

def get_session_db_path() -> Path:
    """获取会话数据库路径"""
    db_dir = Path.home() / ".openclaw" / "sessions"
    db_dir.mkdir(parents=True, exist_ok=True)
    return db_dir / "sessions.db"

# =============================================================================
# 数据类
# =============================================================================

@dataclass
class Session:
    """会话数据"""
    id: str
    title: str
    created_at: float
    updated_at: float
    message_count: int
    metadata: Dict[str, Any]

@dataclass  
class Message:
    """消息数据"""
    id: int
    session_id: str
    role: str  # user/assistant/system
    content: str
    created_at: float
    metadata: Dict[str, Any]

# =============================================================================
# SessionManager
# =============================================================================

class SessionManager:
    """
    会话管理器
    
    支持：
    - 创建新会话
    - 恢复会话
    - 保存消息
    - 列出最近会话
    """
    
    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or get_session_db_path()
        self._init_db()
    
    def _init_db(self):
        """初始化数据库"""
        conn = sqlite3.connect(str(self.db_path))
        conn.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL DEFAULT '新会话',
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL,
                message_count INTEGER DEFAULT 0,
                metadata TEXT DEFAULT '{}'
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at REAL NOT NULL,
                metadata TEXT DEFAULT '{}',
                FOREIGN KEY (session_id) REFERENCES sessions(id)
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_messages_session 
            ON messages(session_id, created_at)
        """)
        conn.commit()
        conn.close()
    
    def create_session(self, title: str = "新会话", metadata: Optional[Dict] = None) -> Session:
        """创建新会话"""
        import uuid
        
        session_id = str(uuid.uuid4())[:12]
        now = time.time()
        
        conn = sqlite3.connect(str(self.db_path))
        conn.execute("""
            INSERT INTO sessions (id, title, created_at, updated_at, message_count, metadata)
            VALUES (?, ?, ?, ?, 0, ?)
        """, (session_id, title, now, now, json.dumps(metadata or {})))
        conn.commit()
        conn.close()
        
        return Session(
            id=session_id,
            title=title,
            created_at=now,
            updated_at=now,
            message_count=0,
            metadata=metadata or {}
        )
    
    def get_session(self, session_id: str) -> Optional[Session]:
        """获取会话"""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.execute("""
            SELECT id, title, created_at, updated_at, message_count, metadata
            FROM sessions WHERE id = ?
        """, (session_id,))
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return None
        
        return Session(
            id=row[0],
            title=row[1],
            created_at=row[2],
            updated_at=row[3],
            message_count=row[4],
            metadata=json.loads(row[5] or '{}')
        )
    
    def list_sessions(self, limit: int = 20) -> List[Session]:
        """列出最近会话"""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.execute("""
            SELECT id, title, created_at, updated_at, message_count, metadata
            FROM sessions
            ORDER BY updated_at DESC
            LIMIT ?
        """, (limit,))
        rows = cursor.fetchall()
        conn.close()
        
        return [
            Session(
                id=row[0],
                title=row[1],
                created_at=row[2],
                updated_at=row[3],
                message_count=row[4],
                metadata=json.loads(row[5] or '{}')
            )
            for row in rows
        ]
    
    def add_message(self, session_id: str, role: str, content: str, 
                   metadata: Optional[Dict] = None) -> Message:
        """添加消息到会话"""
        now = time.time()
        
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.execute("""
            INSERT INTO messages (session_id, role, content, created_at, metadata)
            VALUES (?, ?, ?, ?, ?)
        """, (session_id, role, content, now, json.dumps(metadata or {})))
        message_id = cursor.lastrowid
        
        # 更新会话的updated_at和message_count
        conn.execute("""
            UPDATE sessions 
            SET updated_at = ?, message_count = message_count + 1
            WHERE id = ?
        """, (now, session_id))
        
        conn.commit()
        conn.close()
        
        return Message(
            id=message_id,
            session_id=session_id,
            role=role,
            content=content,
            created_at=now,
            metadata=metadata or {}
        )
    
    def get_messages(self, session_id: str, limit: int = 100) -> List[Message]:
        """获取会话消息"""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.execute("""
            SELECT id, session_id, role, content, created_at, metadata
            FROM messages
            WHERE session_id = ?
            ORDER BY created_at ASC
            LIMIT ?
        """, (session_id, limit))
        rows = cursor.fetchall()
        conn.close()
        
        return [
            Message(
                id=row[0],
                session_id=row[1],
                role=row[2],
                content=row[3],
                created_at=row[4],
                metadata=json.loads(row[5] or '{}')
            )
            for row in rows
        ]
    
    def update_title(self, session_id: str, title: str):
        """更新会话标题"""
        conn = sqlite3.connect(str(self.db_path))
        conn.execute("""
            UPDATE sessions SET title = ?, updated_at = ? WHERE id = ?
        """, (title, time.time(), session_id))
        conn.commit()
        conn.close()
    
    def delete_session(self, session_id: str):
        """删除会话"""
        conn = sqlite3.connect(str(self.db_path))
        conn.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
        conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
        conn.commit()
        conn.close()
    
    def get_or_create_session(self, session_id: Optional[str] = None) -> Session:
        """获取或创建会话"""
        if session_id:
            session = self.get_session(session_id)
            if session:
                return session
        
        return self.create_session()
