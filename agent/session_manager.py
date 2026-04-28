"""
MimirAether Session Manager
会话状态管理器 - 基于Hermes Agent设计
"""
import json
import os
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List
import threading
import uuid

class SessionManager:
    """会话管理器 - 管理对话状态、检查点、和上下文"""
    
    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            db_path = os.path.expanduser("~/.openclaw/projects/MimirAether/sessions.db")
        
        self.db_path = db_path
        self.db_dir = os.path.dirname(db_path)
        if self.db_dir:
            os.makedirs(self.db_dir, exist_ok=True)
        
        self._local = threading.local()
        self._init_db()
    
    def _get_conn(self) -> sqlite3.Connection:
        if not hasattr(self._local, 'conn'):
            self._local.conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self._local.conn.row_factory = sqlite3.Row
        return self._local.conn
    
    def _init_db(self):
        """初始化数据库表"""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                title TEXT,
                metadata TEXT,
                active INTEGER DEFAULT 1
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS checkpoints (
                id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                created_at TEXT NOT NULL,
                context_snapshot TEXT NOT NULL,
                description TEXT,
                FOREIGN KEY (session_id) REFERENCES sessions(id)
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                event_type TEXT NOT NULL,
                data TEXT,
                FOREIGN KEY (session_id) REFERENCES sessions(id)
            )
        """)
        
        conn.commit()
    
    def create_session(self, title: Optional[str] = None, metadata: Optional[Dict] = None) -> str:
        """创建新会话"""
        session_id = str(uuid.uuid4())[:8]
        now = datetime.now().isoformat()
        
        conn = self._get_conn()
        cursor = conn.cursor()
        
        cursor.execute(
            'INSERT INTO sessions (id, created_at, updated_at, title, metadata, active) VALUES (?, ?, ?, ?, ?, ?)',
            (session_id, now, now, title, json.dumps(metadata or {}), 1)
        )
        
        conn.commit()
        return session_id
    
    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """获取会话信息"""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM sessions WHERE id = ?', (session_id,))
        row = cursor.fetchone()
        if row:
            return dict(row)
        return None
    
    def list_sessions(self, limit: int = 20, active_only: bool = True) -> List[Dict]:
        """列出所有会话"""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        query = 'SELECT * FROM sessions'
        if active_only:
            query += ' WHERE active = 1'
        query += ' ORDER BY updated_at DESC LIMIT ?'
        
        cursor.execute(query, (limit,))
        return [dict(row) for row in cursor.fetchall()]
    
    def update_session(self, session_id: str, **kwargs):
        """更新会话"""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        updates = []
        values = []
        
        for key, value in kwargs.items():
            if key in ('title', 'metadata', 'active'):
                updates.append(f"{key} = ?")
                values.append(json.dumps(value) if key == 'metadata' else value)
        
        if updates:
            updates.append("updated_at = ?")
            values.append(datetime.now().isoformat())
            values.append(session_id)
            cursor.execute(f'UPDATE sessions SET {", ".join(updates)} WHERE id = ?', values)
            conn.commit()
    
    def delete_session(self, session_id: str):
        """软删除会话"""
        self.update_session(session_id, active=0)
    
    def create_checkpoint(self, session_id: str, context_snapshot: Dict[str, Any], description: Optional[str] = None) -> str:
        """创建检查点"""
        checkpoint_id = str(uuid.uuid4())[:12]
        now = datetime.now().isoformat()
        
        conn = self._get_conn()
        cursor = conn.cursor()
        
        cursor.execute(
            'INSERT INTO checkpoints (id, session_id, created_at, context_snapshot, description) VALUES (?, ?, ?, ?, ?)',
            (checkpoint_id, session_id, now, json.dumps(context_snapshot), description)
        )
        
        conn.commit()
        return checkpoint_id
    
    def get_checkpoint(self, checkpoint_id: str) -> Optional[Dict[str, Any]]:
        """获取检查点"""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM checkpoints WHERE id = ?', (checkpoint_id,))
        row = cursor.fetchone()
        if row:
            return dict(row)
        return None
    
    def list_checkpoints(self, session_id: str) -> List[Dict]:
        """列出会话的所有检查点"""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM checkpoints WHERE session_id = ? ORDER BY created_at DESC', (session_id,))
        return [dict(row) for row in cursor.fetchall()]
    
    def delete_checkpoint(self, checkpoint_id: str):
        """删除检查点"""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute('DELETE FROM checkpoints WHERE id = ?', (checkpoint_id,))
        conn.commit()
    
    def log_event(self, session_id: str, event_type: str, data: Optional[Dict] = None):
        """记录事件"""
        now = datetime.now().isoformat()
        
        conn = self._get_conn()
        cursor = conn.cursor()
        
        cursor.execute(
            'INSERT INTO events (session_id, timestamp, event_type, data) VALUES (?, ?, ?, ?)',
            (session_id, now, event_type, json.dumps(data or {}))
        )
        
        conn.commit()
    
    def get_events(self, session_id: str, event_type: Optional[str] = None, limit: int = 100) -> List[Dict]:
        """获取事件历史"""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        query = 'SELECT * FROM events WHERE session_id = ?'
        params = [session_id]
        
        if event_type:
            query += ' AND event_type = ?'
            params.append(event_type)
        
        query += ' ORDER BY timestamp DESC LIMIT ?'
        params.append(limit)
        
        cursor.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]
    
    def get_session_stats(self, session_id: str) -> Dict[str, Any]:
        """获取会话统计"""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        cursor.execute('SELECT COUNT(*) FROM checkpoints WHERE session_id = ?', (session_id,))
        checkpoint_count = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) FROM events WHERE session_id = ?', (session_id,))
        event_count = cursor.fetchone()[0]
        
        cursor.execute('SELECT event_type, COUNT(*) as count FROM events WHERE session_id = ? GROUP BY event_type', (session_id,))
        events_by_type = {row['event_type']: row['count'] for row in cursor.fetchall()}
        
        return {
            'session_id': session_id,
            'checkpoint_count': checkpoint_count,
            'event_count': event_count,
            'events_by_type': events_by_type
        }
    
    def close(self):
        """关闭数据库连接"""
        if hasattr(self._local, 'conn'):
            self._local.conn.close()
            del self._local.conn


_session_manager = None

def get_session_manager() -> SessionManager:
    """获取全局会话管理器实例"""
    global _session_manager
    if _session_manager is None:
        _session_manager = SessionManager()
    return _session_manager


if __name__ == '__main__':
    sm = SessionManager()
    session_id = sm.create_session(title="Test Session", metadata={"source": "test"})
    print(f"Created session: {session_id}")
    
    checkpoint_id = sm.create_checkpoint(session_id, {"messages": [{"role": "user", "content": "Hello"}]}, "Initial state")
    print(f"Created checkpoint: {checkpoint_id}")
    
    sm.log_event(session_id, "user_message", {"content": "Hello"})
    sm.log_event(session_id, "assistant_message", {"content": "Hi there!"})
    
    stats = sm.get_session_stats(session_id)
    print(f"Stats: {stats}")
    
    checkpoints = sm.list_checkpoints(session_id)
    print(f"Checkpoints: {len(checkpoints)}")
    
    sm.close()
    print("Session manager test completed!")
