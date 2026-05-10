"""
会话状态追踪模块 - SessionTracker
使用 SQLite 存储会话信息，支持会话创建、事件记录、状态查询
新增: Token统计功能 (参考Hermes SessionDB)
"""

import sqlite3
import json
import os
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from pathlib import Path


# Token单价 (USD per 1M tokens) - OpenAI GPT-4o mini基准
TOKEN_PRICING = {
    "input": 0.15,      # $0.15 / 1M input tokens
    "output": 0.60,     # $0.60 / 1M output tokens
    "cache_read": 0.01, # $0.01 / 1M cache read (命中)
    "cache_write": 0.11 # $0.11 / 1M cache write
}


class SessionTracker:
    """会话状态追踪模块 - 使用 SQLite 存储会话信息"""
    
    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            from mimir_constants import get_mimir_sessions_dir

            base_dir = str(get_mimir_sessions_dir())
            os.makedirs(base_dir, exist_ok=True)
            db_path = os.path.join(base_dir, "sessions.db")
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self):
        """初始化数据库表"""
        with sqlite3.connect(self.db_path) as conn:
            # 基础表
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    metadata TEXT DEFAULT '{}',
                    is_active INTEGER DEFAULT 1
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS session_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    event_data TEXT DEFAULT '{}',
                    timestamp TEXT NOT NULL,
                    FOREIGN KEY (session_id) REFERENCES sessions(session_id)
                )
            """)
            # 索引优化
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_sessions_updated 
                ON sessions(updated_at DESC)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_events_session 
                ON session_events(session_id, timestamp)
            """)
            conn.commit()
            # 迁移: 添加Token统计字段
            self._migrate_token_fields(conn)
    
    def _migrate_token_fields(self, conn: sqlite3.Connection):
        """迁移数据库，添加Token统计字段"""
        cursor = conn.execute("PRAGMA table_info(sessions)")
        columns = {row[1] for row in cursor.fetchall()}
        
        token_fields = {
            "input_tokens": "INTEGER DEFAULT 0",
            "output_tokens": "INTEGER DEFAULT 0",
            "cache_read_tokens": "INTEGER DEFAULT 0",
            "cache_write_tokens": "INTEGER DEFAULT 0",
            "total_tokens": "INTEGER DEFAULT 0",
            "estimated_cost_usd": "REAL DEFAULT 0.0",
            "last_prompt_tokens": "INTEGER DEFAULT 0",
            "memory_flushed": "INTEGER DEFAULT 0"
        }
        
        for field, definition in token_fields.items():
            if field not in columns:
                conn.execute(f"ALTER TABLE sessions ADD COLUMN {field} {definition}")
        conn.commit()
    
    def _now(self) -> str:
        """获取当前UTC时间ISO格式"""
        return datetime.now(timezone.utc).isoformat()
    
    def create_session(self, session_id: str, metadata: Optional[Dict] = None) -> bool:
        """创建新会话
        
        Args:
            session_id: 会话唯一标识符
            metadata: 会话元数据 (dict)
            
        Returns:
            bool: 创建成功返回 True，已存在返回 False
        """
        now = self._now()
        metadata_json = json.dumps(metadata or {})
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    """INSERT INTO sessions (session_id, created_at, updated_at, metadata) 
                       VALUES (?, ?, ?, ?)""",
                    (session_id, now, now, metadata_json)
                )
                conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False  # 会话已存在
    
    def end_session(self, session_id: str) -> bool:
        """结束会话
        
        Args:
            session_id: 会话唯一标识符
            
        Returns:
            bool: 成功返回 True，会话不存在返回 False
        """
        now = self._now()
        with sqlite3.connect(self.db_path) as conn:
            result = conn.execute(
                """UPDATE sessions SET is_active = 0, updated_at = ? 
                   WHERE session_id = ?""",
                (now, session_id)
            )
            conn.commit()
            return result.rowcount > 0
    
    def record_event(self, session_id: str, event_type: str, 
                     event_data: Optional[Dict] = None) -> bool:
        """记录会话事件
        
        Args:
            session_id: 会话唯一标识符
            event_type: 事件类型
            event_data: 事件数据 (dict)
            
        Returns:
            bool: 成功返回 True，会话不存在返回 False
        """
        now = self._now()
        event_data_json = json.dumps(event_data or {})
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    """INSERT INTO session_events (session_id, event_type, event_data, timestamp)
                       VALUES (?, ?, ?, ?)""",
                    (session_id, event_type, event_data_json, now)
                )
                conn.execute(
                    """UPDATE sessions SET updated_at = ? WHERE session_id = ?""",
                    (now, session_id)
                )
                conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False
    
    def get_session(self, session_id: str) -> Optional[Dict]:
        """获取会话信息
        
        Args:
            session_id: 会话唯一标识符
            
        Returns:
            dict: 会话信息，不存在返回 None
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM sessions WHERE session_id = ?", (session_id,)
            ).fetchone()
            if row:
                return {
                    "session_id": row["session_id"],
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"],
                    "metadata": json.loads(row["metadata"]),
                    "is_active": bool(row["is_active"]),
                    # Token统计
                    "input_tokens": row["input_tokens"],
                    "output_tokens": row["output_tokens"],
                    "cache_read_tokens": row["cache_read_tokens"],
                    "cache_write_tokens": row["cache_write_tokens"],
                    "total_tokens": row["total_tokens"],
                    "estimated_cost_usd": row["estimated_cost_usd"],
                    "last_prompt_tokens": row["last_prompt_tokens"],
                    "memory_flushed": row["memory_flushed"]
                }
        return None
    
    def get_active_sessions(self) -> List[Dict]:
        """获取所有活跃会话
        
        Returns:
            list: 活跃会话列表，按更新时间倒序
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM sessions WHERE is_active = 1 ORDER BY updated_at DESC"
            ).fetchall()
            return [
                {
                    "session_id": row["session_id"],
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"],
                    "metadata": json.loads(row["metadata"]),
                    "total_tokens": row["total_tokens"],
                    "estimated_cost_usd": row["estimated_cost_usd"]
                }
                for row in rows
            ]
    
    def get_session_events(self, session_id: str) -> List[Dict]:
        """获取会话的所有事件
        
        Args:
            session_id: 会话唯一标识符
            
        Returns:
            list: 事件列表，按时间戳升序
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                """SELECT * FROM session_events WHERE session_id = ? 
                   ORDER BY timestamp ASC""",
                (session_id,)
            ).fetchall()
            return [
                {
                    "id": row["id"],
                    "event_type": row["event_type"],
                    "event_data": json.loads(row["event_data"]),
                    "timestamp": row["timestamp"]
                }
                for row in rows
            ]
    
    # ========== Token统计功能 (新增) ==========
    
    def update_token_stats(self, session_id: str, 
                          input_tokens: int = 0,
                          output_tokens: int = 0,
                          cache_read_tokens: int = 0,
                          cache_write_tokens: int = 0) -> bool:
        """更新Token统计
        
        基于Hermes SessionDB实现，追踪会话的Token使用情况
        
        Args:
            session_id: 会话ID
            input_tokens: 输入Token数
            output_tokens: 输出Token数
            cache_read_tokens: 缓存读取Token数
            cache_write_tokens: 缓存写入Token数
            
        Returns:
            bool: 更新成功返回True
        """
        with sqlite3.connect(self.db_path) as conn:
            # 累计统计
            conn.execute("""
                UPDATE sessions SET
                    input_tokens = input_tokens + ?,
                    output_tokens = output_tokens + ?,
                    cache_read_tokens = cache_read_tokens + ?,
                    cache_write_tokens = cache_write_tokens + ?,
                    last_prompt_tokens = ?,
                    total_tokens = total_tokens + ? + ? + ? + ?,
                    estimated_cost_usd = estimated_cost_usd + ?,
                    updated_at = ?
                WHERE session_id = ?
            """, (
                input_tokens, output_tokens, cache_read_tokens, cache_write_tokens,
                input_tokens,  # last_prompt_tokens = 当前prompt的input
                input_tokens, output_tokens, cache_read_tokens, cache_write_tokens,
                self._calculate_cost(input_tokens, output_tokens, cache_read_tokens, cache_write_tokens),
                self._now(),
                session_id
            ))
            conn.commit()
            return conn.total_changes > 0
    
    def _calculate_cost(self, input_t: int, output_t: int, 
                        cache_read: int, cache_write: int) -> float:
        """计算USD成本
        
        Args:
            input_t: 输入Token数
            output_t: 输出Token数
            cache_read: 缓存读取Token数
            cache_write: 缓存写入Token数
            
        Returns:
            float: 估算成本 (USD)
        """
        return (
            input_t * TOKEN_PRICING["input"] / 1_000_000 +
            output_t * TOKEN_PRICING["output"] / 1_000_000 +
            cache_read * TOKEN_PRICING["cache_read"] / 1_000_000 +
            cache_write * TOKEN_PRICING["cache_write"] / 1_000_000
        )
    
    def record_memory_flush(self, session_id: str) -> bool:
        """记录记忆压缩事件
        
        Args:
            session_id: 会话ID
            
        Returns:
            bool: 成功返回True
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                UPDATE sessions SET
                    memory_flushed = memory_flushed + 1,
                    updated_at = ?
                WHERE session_id = ?
            """, (self._now(), session_id))
            conn.commit()
            return conn.total_changes > 0
    
    def get_session_stats(self, session_id: str) -> Optional[Dict]:
        """获取会话的统计摘要
        
        Args:
            session_id: 会话ID
            
        Returns:
            dict: 统计摘要，失败返回None
        """
        session = self.get_session(session_id)
        if not session:
            return None
        return {
            "session_id": session_id,
            "total_tokens": session["total_tokens"],
            "estimated_cost_usd": round(session["estimated_cost_usd"], 6),
            "memory_flushes": session["memory_flushed"],
            "token_breakdown": {
                "input": session["input_tokens"],
                "output": session["output_tokens"],
                "cache_read": session["cache_read_tokens"],
                "cache_write": session["cache_write_tokens"]
            }
        }
    
    def get_cost_ranking(self, limit: int = 10) -> List[Dict]:
        """获取成本最高的会话排名
        
        Args:
            limit: 返回数量
            
        Returns:
            list: 按成本排序的会话列表
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute("""
                SELECT session_id, total_tokens, estimated_cost_usd, created_at
                FROM sessions
                WHERE is_active = 1
                ORDER BY estimated_cost_usd DESC
                LIMIT ?
            """, (limit,)).fetchall()
            return [
                {
                    "session_id": row["session_id"],
                    "total_tokens": row["total_tokens"],
                    "estimated_cost_usd": round(row["estimated_cost_usd"], 6),
                    "created_at": row["created_at"]
                }
                for row in rows
            ]

    # ========== 上下文管理器支持 ==========
    
    def __enter__(self) -> 'SessionTracker':
        """进入上下文管理器
        
        用法:
            with SessionTracker() as tracker:
                tracker.create_session("session_1")
                tracker.record_event("session_1", "test")
        
        Returns:
            SessionTracker: 返回自身实例
        """
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        """退出上下文管理器
        
        自动清理资源。本模块使用即开即连模式，
        各方法内部管理 SQLite 连接，此处无需额外清理。
        
        Args:
            exc_type: 异常类型 (如有)
            exc_val: 异常值 (如有)
            exc_tb: 异常回溯 (如有)
            
        Returns:
            bool: 返回 False 表示不阻止异常传播
        """
        # 可扩展：添加会话关闭日志、资源释放等
        return False



# 使用示例
if __name__ == "__main__":
    # 初始化追踪器
    tracker = SessionTracker()
    
    # 创建新会话
    session_id = "demo_session"
    tracker.create_session(session_id, {"user": "demo", "purpose": "示例"})
    
    # 记录事件
    tracker.record_event(session_id, "task_started", {"task": "数据分析"})
    
    # 更新Token统计 (模拟LLM调用)
    tracker.update_token_stats(
        session_id,
        input_tokens=5000,
        output_tokens=1500
    )
    tracker.update_token_stats(
        session_id,
        input_tokens=8000,
        output_tokens=2000
    )
    
    # 获取会话信息
    session = tracker.get_session(session_id)
    print(f"会话: {session['session_id']}")
    print(f"总Tokens: {session['total_tokens']}")
    print(f"估算成本: ${session['estimated_cost_usd']:.6f}")
    
    # 获取统计摘要
    stats = tracker.get_session_stats(session_id)
    print(f"统计: {stats}")
    
    # 获取事件历史
    events = tracker.get_session_events(session_id)
    for event in events:
        print(f"  [{event['timestamp']}] {event['event_type']}")
    
    # 结束会话
    tracker.end_session(session_id)
