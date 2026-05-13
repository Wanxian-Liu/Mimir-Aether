"""
⚠️ DEPRECATED: MimirAether Tool Registry (SQLite)
工具注册表 - 管理所有可用工具的元数据（SQLite 存储）

此模块为工具**库存/分析**用途（enable/disable/search/stats/log_call），
**不是**运行时工具执行路径。运行时使用 tools.registry.registry（Hermes 模式）。
仅在 agent/test_tool_registry_api.py 和 agent/test_tool_registry_concurrency.py 
的 Parity 测试中使用。
"""
import json
import os
import sqlite3
from datetime import datetime
from typing import Optional, Dict, Any, List, Callable
import threading
import uuid

class ToolMetadata:
    """工具元数据"""
    
    def __init__(self, name: str, category: str, description: str, 
                 function: Optional[Callable] = None, **kwargs):
        self.name = name
        self.category = category
        self.description = description
        self.function = function
        self.extra = kwargs
        self.registered_at = datetime.now().isoformat()
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "category": self.category,
            "description": self.description,
            "registered_at": self.registered_at,
            **{k: v for k, v in self.extra.items() if not k.startswith('_')}
        }


class ToolRegistry:
    """工具注册表 - 统一管理所有MCP工具"""
    
    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            from mimir_constants import get_mimir_home

            db_path = str(get_mimir_home() / "tools.db")
        
        self.db_path = db_path
        self.db_dir = os.path.dirname(db_path)
        if self.db_dir:
            os.makedirs(self.db_dir, exist_ok=True)
        
        self._local = threading.local()
        self._tools: Dict[str, ToolMetadata] = {}
        self._init_db()
    
    def _get_conn(self) -> sqlite3.Connection:
        if not hasattr(self._local, 'conn'):
            self._local.conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self._local.conn.row_factory = sqlite3.Row
            # WAL lets readers see fresh commits from other threads without classic
            # journal writer starvation (important for gateway/agent concurrent access).
            self._local.conn.execute("PRAGMA journal_mode=WAL")
        return self._local.conn
    
    def _init_db(self):
        """初始化数据库"""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tools (
                id TEXT PRIMARY KEY,
                name TEXT UNIQUE NOT NULL,
                category TEXT NOT NULL,
                description TEXT,
                schema TEXT,
                metadata TEXT,
                enabled INTEGER DEFAULT 1,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tool_calls (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tool_name TEXT NOT NULL,
                called_at TEXT NOT NULL,
                success INTEGER,
                duration_ms REAL,
                error TEXT,
                metadata TEXT
            )
        """)
        
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_tools_name ON tools(name)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_tools_category ON tools(category)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_calls_tool ON tool_calls(tool_name)")
        
        conn.commit()
    
    def register(self, name: str, category: str, description: str, 
                 schema: Optional[Dict] = None, **metadata) -> bool:
        """注册工具"""
        tool_id = str(uuid.uuid4())[:12]
        now = datetime.now().isoformat()
        
        conn = self._get_conn()
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                INSERT INTO tools (id, name, category, description, schema, metadata, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (tool_id, name, category, description, json.dumps(schema or {}), 
                  json.dumps(metadata), now, now))
            
            conn.commit()
            
            self._tools[name] = ToolMetadata(name, category, description, **metadata)
            return True
        except sqlite3.IntegrityError:
            # 工具已存在，更新
            cursor.execute("""
                UPDATE tools SET category=?, description=?, schema=?, metadata=?, updated_at=?
                WHERE name=?
            """, (category, description, json.dumps(schema or {}), json.dumps(metadata), now, name))
            conn.commit()
            
            self._tools[name] = ToolMetadata(name, category, description, **metadata)
            return True
    
    def unregister(self, name: str) -> bool:
        """注销工具"""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        cursor.execute('DELETE FROM tools WHERE name = ?', (name,))
        conn.commit()
        
        if name in self._tools:
            del self._tools[name]
        
        return cursor.rowcount > 0
    
    def get(self, name: str) -> Optional[Dict[str, Any]]:
        """获取工具信息"""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM tools WHERE name = ? AND enabled = 1', (name,))
        row = cursor.fetchone()
        
        if row:
            return dict(row)
        return None
    
    def list_all(self, category: Optional[str] = None, enabled_only: bool = True) -> List[Dict]:
        """列出工具"""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        query = 'SELECT * FROM tools'
        conditions = []
        params = []
        
        if enabled_only:
            conditions.append('enabled = 1')
        
        if category:
            conditions.append('category = ?')
            params.append(category)
        
        if conditions:
            query += ' WHERE ' + ' AND '.join(conditions)
        
        query += ' ORDER BY category, name'
        
        cursor.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]
    
    def list_categories(self) -> List[str]:
        """列出所有分类"""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        cursor.execute('SELECT DISTINCT category FROM tools WHERE enabled = 1 ORDER BY category')
        return [row['category'] for row in cursor.fetchall()]
    
    def enable(self, name: str) -> bool:
        """启用工具"""
        return self._set_enabled(name, True)
    
    def disable(self, name: str) -> bool:
        """禁用工具"""
        return self._set_enabled(name, False)
    
    def _set_enabled(self, name: str, enabled: bool) -> bool:
        conn = self._get_conn()
        cursor = conn.cursor()
        
        cursor.execute('UPDATE tools SET enabled = ?, updated_at = ? WHERE name = ?',
                      (1 if enabled else 0, datetime.now().isoformat(), name))
        conn.commit()
        
        return cursor.rowcount > 0
    
    def log_call(self, tool_name: str, success: bool, duration_ms: float = 0,
                 error: Optional[str] = None, metadata: Optional[Dict] = None):
        """记录工具调用"""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO tool_calls (tool_name, called_at, success, duration_ms, error, metadata)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (tool_name, datetime.now().isoformat(), 1 if success else 0, 
              duration_ms, error, json.dumps(metadata or {})))
        
        conn.commit()
    
    def get_stats(self, tool_name: Optional[str] = None, days: int = 7) -> Dict[str, Any]:
        """获取工具使用统计"""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        query = """
            SELECT tool_name, COUNT(*) as total_calls,
                   SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as successful_calls,
                   AVG(duration_ms) as avg_duration,
                   MAX(called_at) as last_called
            FROM tool_calls
            WHERE called_at >= datetime('now', '-' || ? || ' days')
        """
        params = [days]
        
        if tool_name:
            query += ' AND tool_name = ?'
            params.append(tool_name)
        
        query += ' GROUP BY tool_name ORDER BY total_calls DESC'
        
        cursor.execute(query, params)
        stats = {row['tool_name']: {
            'total_calls': row['total_calls'],
            'successful_calls': row['successful_calls'],
            'success_rate': row['successful_calls'] / row['total_calls'] if row['total_calls'] > 0 else 0,
            'avg_duration_ms': row['avg_duration'],
            'last_called': row['last_called']
        } for row in cursor.fetchall()}
        
        return stats
    
    def search(self, query: str) -> List[Dict]:
        """搜索工具"""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        search_term = f'%{query}%'
        cursor.execute("""
            SELECT * FROM tools 
            WHERE enabled = 1 AND (name LIKE ? OR description LIKE ? OR category LIKE ?)
            ORDER BY 
                CASE WHEN name LIKE ? THEN 1 ELSE 2 END,
                name
        """, (search_term, search_term, search_term, search_term))
        
        return [dict(row) for row in cursor.fetchall()]
    
    def close(self):
        """关闭数据库连接"""
        if hasattr(self._local, 'conn'):
            self._local.conn.close()
            del self._local.conn


# 全局实例
_registry = None

def get_registry() -> ToolRegistry:
    """获取全局注册表实例"""
    global _registry
    if _registry is None:
        _registry = ToolRegistry()
    return _registry


# 预设工具分类
PRESET_CATEGORIES = {
    'file': '文件系统操作',
    'terminal': '终端命令执行',
    'code': '代码执行与分析',
    'web': '网络请求与搜索',
    'memory': '记忆与持久化',
    'session': '会话管理',
    'mcp': 'MCP协议工具',
    'ai': 'AI模型交互',
    'creative': '创意与生成',
    'productivity': '生产力工具'
}

if __name__ == '__main__':
    registry = ToolRegistry()
    
    # 注册示例工具
    registry.register(
        'file_read', 'file', '读取文件内容',
        schema={'path': {'type': 'string', 'required': True}},
        tags=['file', 'read']
    )
    
    registry.register(
        'terminal_exec', 'terminal', '执行终端命令',
        schema={'command': {'type': 'string', 'required': True}},
        tags=['shell', 'bash']
    )
    
    # 列出所有工具
    tools = registry.list_all()
    print(f"Registered tools: {len(tools)}")
    for t in tools:
        print(f"  - {t['name']} ({t['category']})")
    
    # 列出分类
    categories = registry.list_categories()
    print(f"\nCategories: {categories}")
    
    # 搜索
    results = registry.search('file')
    print(f"\nSearch 'file': {len(results)} results")
    
    # 记录调用
    registry.log_call('file_read', True, 15.5)
    registry.log_call('terminal_exec', False, 0, 'Timeout')
    
    # 统计
    stats = registry.get_stats()
    print(f"\nStats: {stats}")
    
    registry.close()
    print("\nTool registry test completed!")
