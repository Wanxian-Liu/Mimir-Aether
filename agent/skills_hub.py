"""
MimirAether Skills Hub
技能中心 - 管理和分发技能模块
"""
import json
import os
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List, Callable
import threading
import uuid
import importlib.util
import inspect

class SkillMetadata:
    """技能元数据"""
    
    REQUIRED_FIELDS = ['name', 'description']
    OPTIONAL_FIELDS = ['category', 'tags', 'author', 'version', 'dependencies']
    
    def __init__(self, name: str, description: str, category: str = 'general',
                 tags: Optional[List[str]] = None, **kwargs):
        self.name = name
        self.description = description
        self.category = category
        self.tags = tags or []
        self.author = kwargs.get('author', 'unknown')
        self.version = kwargs.get('version', '1.0.0')
        self.dependencies = kwargs.get('dependencies', [])
        self.created_at = datetime.now().isoformat()
        self.updated_at = self.created_at
        self._path = None
        self._loader = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'name': self.name,
            'description': self.description,
            'category': self.category,
            'tags': self.tags,
            'author': self.author,
            'version': self.version,
            'dependencies': self.dependencies,
            'created_at': self.created_at,
            'updated_at': self.updated_at,
            'path': self._path
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'SkillMetadata':
        meta = cls(
            name=data['name'],
            description=data['description'],
            category=data.get('category', 'general'),
            tags=data.get('tags', []),
            author=data.get('author'),
            version=data.get('version'),
            dependencies=data.get('dependencies', [])
        )
        meta.created_at = data.get('created_at', datetime.now().isoformat())
        meta.updated_at = data.get('updated_at', meta.created_at)
        meta._path = data.get('path')
        return meta


class SkillsHub:
    """技能中心 - 管理所有技能模块"""
    
    DEFAULT_SKILLS_DIR = os.path.expanduser('~/.openclaw/projects/MimirAether/skills')
    
    def __init__(self, db_path: Optional[str] = None, skills_dir: Optional[str] = None):
        if db_path is None:
            db_path = os.path.expanduser('~/.openclaw/projects/MimirAether/skills_hub.db')
        
        self.db_path = db_path
        self.skills_dir = skills_dir or self.DEFAULT_SKILLS_DIR
        
        os.makedirs(self.skills_dir, exist_ok=True)
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        
        self._local = threading.local()
        self._cache: Dict[str, SkillMetadata] = {}
        self._loaded_modules: Dict[str, Any] = {}
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
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS skills (
                id TEXT PRIMARY KEY,
                name TEXT UNIQUE NOT NULL,
                description TEXT,
                category TEXT,
                tags TEXT,
                author TEXT,
                version TEXT,
                dependencies TEXT,
                file_path TEXT,
                enabled INTEGER DEFAULT 1,
                use_count INTEGER DEFAULT 0,
                last_used TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS skill_executions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                skill_name TEXT NOT NULL,
                executed_at TEXT NOT NULL,
                duration_ms REAL,
                success INTEGER,
                error TEXT,
                input_summary TEXT,
                output_summary TEXT
            )
        """)
        
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_skills_name ON skills(name)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_skills_category ON skills(category)")
        
        conn.commit()
    
    def register(self, skill: SkillMetadata, file_path: Optional[str] = None) -> bool:
        """注册技能"""
        skill_id = str(uuid.uuid4())[:12]
        now = datetime.now().isoformat()
        
        conn = self._get_conn()
        cursor = conn.cursor()
        
        path = file_path or skill._path or os.path.join(self.skills_dir, f"{skill.name}.md")
        
        try:
            cursor.execute("""
                INSERT INTO skills (id, name, description, category, tags, author, version, 
                                   dependencies, file_path, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (skill_id, skill.name, skill.description, skill.category, 
                  json.dumps(skill.tags), skill.author, skill.version,
                  json.dumps(skill.dependencies), path, now, now))
            
            conn.commit()
            
            skill._path = path
            self._cache[skill.name] = skill
            return True
            
        except sqlite3.IntegrityError:
            # 更新已存在的技能
            cursor.execute("""
                UPDATE skills SET description=?, category=?, tags=?, author=?, version=?,
                                 dependencies=?, updated_at=?
                WHERE name=?
            """, (skill.description, skill.category, json.dumps(skill.tags), skill.author,
                  skill.version, json.dumps(skill.dependencies), now, skill.name))
            conn.commit()
            
            skill._path = path
            self._cache[skill.name] = skill
            return True
    
    def unregister(self, name: str) -> bool:
        """注销技能"""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        cursor.execute('DELETE FROM skills WHERE name = ?', (name,))
        conn.commit()
        
        if name in self._cache:
            del self._cache[name]
        if name in self._loaded_modules:
            del self._loaded_modules[name]
        
        return cursor.rowcount > 0
    
    def get(self, name: str) -> Optional[SkillMetadata]:
        """获取技能元数据"""
        if name in self._cache:
            return self._cache[name]
        
        conn = self._get_conn()
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM skills WHERE name = ?', (name,))
        row = cursor.fetchone()
        
        if row:
            data = dict(row)
            data['tags'] = json.loads(data.get('tags', '[]'))
            data['dependencies'] = json.loads(data.get('dependencies', '[]'))
            
            skill = SkillMetadata.from_dict(data)
            self._cache[name] = skill
            return skill
        
        return None
    
    def list_all(self, category: Optional[str] = None, tags: Optional[List[str]] = None,
                 enabled_only: bool = True) -> List[Dict]:
        """列出技能"""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        query = 'SELECT * FROM skills'
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
        results = [dict(row) for row in cursor.fetchall()]
        
        # 过滤标签
        if tags:
            results = [r for r in results 
                      if any(t in json.loads(r.get('tags', '[]')) for t in tags)]
        
        return results
    
    def list_categories(self) -> List[str]:
        """列出所有分类"""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        cursor.execute('SELECT DISTINCT category FROM skills WHERE enabled = 1 ORDER BY category')
        return [row['category'] for row in cursor.fetchall()]
    
    def search(self, query: str) -> List[Dict]:
        """搜索技能"""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        search_term = f'%{query}%'
        cursor.execute("""
            SELECT * FROM skills 
            WHERE enabled = 1 AND (
                name LIKE ? OR description LIKE ? OR 
                category LIKE ? OR tags LIKE ?
            )
            ORDER BY use_count DESC, name
        """, (search_term, search_term, search_term, search_term))
        
        return [dict(row) for row in cursor.fetchall()]
    
    def load_skill_module(self, name: str) -> Optional[Any]:
        """动态加载技能模块"""
        skill = self.get(name)
        if not skill or not skill._path:
            return None
        
        if name in self._loaded_modules:
            return self._loaded_modules[name]
        
        path = Path(skill._path)
        if not path.exists():
            return None
        
        try:
            if path.suffix == '.py':
                spec = importlib.util.spec_from_file_location(name, path)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                self._loaded_modules[name] = module
                return module
            elif path.suffix == '.md':
                # Markdown技能 - 返回文件内容
                with open(path, 'r') as f:
                    content = f.read()
                self._loaded_modules[name] = content
                return content
            
        except Exception as e:
            print(f"Failed to load skill {name}: {e}")
            return None
    
    def execute(self, name: str, context: Optional[Dict] = None, **kwargs) -> Dict[str, Any]:
        """执行技能"""
        start = datetime.now()
        skill = self.get(name)
        
        if not skill:
            return {'success': False, 'error': f'Skill {name} not found'}
        
        # 更新使用计数
        self._increment_usage(name)
        
        result = {
            'skill': name,
            'success': True,
            'started_at': start.isoformat(),
            'output': None
        }
        
        try:
            module = self.load_skill_module(name)
            if module and hasattr(module, 'execute'):
                result['output'] = module.execute(context or {}, **kwargs)
            elif isinstance(module, str):
                result['output'] = module
            else:
                result['output'] = f'Skill {name} loaded (no execute function)'
                
        except Exception as e:
            result['success'] = False
            result['error'] = str(e)
        
        end = datetime.now()
        result['duration_ms'] = (end - start).total_seconds() * 1000
        result['completed_at'] = end.isoformat()
        
        self._log_execution(result)
        
        return result
    
    def _increment_usage(self, name: str):
        """增加使用计数"""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE skills SET use_count = use_count + 1, last_used = ?
            WHERE name = ?
        """, (datetime.now().isoformat(), name))
        conn.commit()
    
    def _log_execution(self, result: Dict):
        """记录执行日志"""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO skill_executions (skill_name, executed_at, duration_ms, success, error)
            VALUES (?, ?, ?, ?, ?)
        """, (result['skill'], result['completed_at'], result.get('duration_ms', 0),
              1 if result['success'] else 0, result.get('error')))
        conn.commit()
    
    def get_stats(self, name: Optional[str] = None) -> Dict[str, Any]:
        """获取技能统计"""
        conn = self._get_conn()
        cursor = conn.cursor()
        
        if name:
            cursor.execute("""
                SELECT * FROM skill_executions 
                WHERE skill_name = ?
                ORDER BY executed_at DESC LIMIT 100
            """, (name,))
            
            return {
                'skill': name,
                'recent_executions': [dict(row) for row in cursor.fetchall()]
            }
        
        cursor.execute("""
            SELECT skill_name, COUNT(*) as total,
                   SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as successful,
                   AVG(duration_ms) as avg_duration
            FROM skill_executions
            GROUP BY skill_name
            ORDER BY total DESC
        """)
        
        return {row['skill_name']: {
            'total_executions': row['total'],
            'successful': row['successful'],
            'success_rate': row['successful'] / row['total'] if row['total'] > 0 else 0,
            'avg_duration_ms': row['avg_duration']
        } for row in cursor.fetchall()}
    
    def create_skill_file(self, name: str, content: str, category: str = 'general') -> str:
        """创建技能文件"""
        path = os.path.join(self.skills_dir, category, f"{name}.md")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        
        with open(path, 'w') as f:
            f.write(content)
        
        return path
    
    def enable(self, name: str) -> bool:
        """启用技能"""
        return self._set_enabled(name, True)
    
    def disable(self, name: str) -> bool:
        """禁用技能"""
        return self._set_enabled(name, False)
    
    def _set_enabled(self, name: str, enabled: bool) -> bool:
        conn = self._get_conn()
        cursor = conn.cursor()
        
        cursor.execute('UPDATE skills SET enabled = ? WHERE name = ?',
                      (1 if enabled else 0, name))
        conn.commit()
        
        return cursor.rowcount > 0
    
    def close(self):
        """关闭数据库连接"""
        if hasattr(self._local, 'conn'):
            self._local.conn.close()
            del self._local.conn


# 全局实例
_hub = None

def get_hub() -> SkillsHub:
    """获取全局技能中心实例"""
    global _hub
    if _hub is None:
        _hub = SkillsHub()
    return _hub


if __name__ == '__main__':
    hub = SkillsHub()
    
    # 创建示例技能
    skill = SkillMetadata(
        name='hello-world',
        description='A simple hello world skill',
        category='example',
        tags=['test', 'demo']
    )
    
    # 创建技能文件
    skill_content = """# Hello World Skill

## Description
A simple demonstration skill

## Usage
```python
def execute(context, **kwargs):
    return "Hello, World!"
```

## Metadata
- Category: example
- Tags: test, demo
"""
    
    skill_path = hub.create_skill_file('hello-world', skill_content, 'example')
    print(f"Created skill file: {skill_path}")
    
    # 注册技能
    skill._path = skill_path
    hub.register(skill)
    
    # 列出所有技能
    skills = hub.list_all()
    print(f"\nTotal skills: {len(skills)}")
    
    # 列出分类
    categories = hub.list_categories()
    print(f"Categories: {categories}")
    
    # 搜索
    results = hub.search('hello')
    print(f"Search 'hello': {len(results)} results")
    
    # 执行
    result = hub.execute('hello-world')
    print(f"\nExecute result: {result}")
    
    # 统计
    stats = hub.get_stats()
    print(f"\nStats: {stats}")
    
    hub.close()
    print("\nSkills hub test completed!")
