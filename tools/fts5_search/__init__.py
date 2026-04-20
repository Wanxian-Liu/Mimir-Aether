"""
MimirAether FTS5 Search Module

跨会话全文搜索模块，提供高性能的FTS5全文索引和搜索能力。

主要组件：
- FTS5SearchEngine: 核心搜索引擎
- BM25Scorer: BM25相关性评分器
- SearchOptions/SearchResult: 数据类
- schema: 数据库Schema定义

使用示例：

```python
from fts5_search import FTS5SearchEngine, SearchOptions

# 创建引擎
engine = FTS5SearchEngine()

# 索引消息
engine.index_message("session-1", "user", "Hello world")

# 搜索
response = engine.search(SearchOptions(query="Hello"))
print(f"Found {response.total_matches} matches")

# 获取统计
stats = engine.get_stats()
print(f"Sessions: {stats['session_count']}")

# 关闭
engine.close()
```

版本: 1.0.0
日期: 2026-04-20
"""

from __future__ import annotations

from .engine import (
    FTS5SearchEngine,
    SearchOptions,
    SearchResult,
    SearchResponse,
    MatchSegment,
    BM25Scorer,
    create_engine,
    quick_search,
)

from .schema import (
    SCHEMA_VERSION,
    SESSIONS_TABLE,
    MESSAGES_TABLE,
    FTS5_SCHEMA,
    SEARCH_HISTORY_TABLE,
    QUERY_CACHE_TABLE,
    INDEX_STATUS_TABLE,
    TRIGGERS,
    INIT_SCRIPT,
    REBUILD_SCRIPT,
    OPTIMIZE_SCRIPT,
)

__version__ = "1.0.0"
__all__ = [
    # 引擎
    "FTS5SearchEngine",
    "SearchOptions",
    "SearchResult", 
    "SearchResponse",
    "MatchSegment",
    "BM25Scorer",
    "create_engine",
    "quick_search",
    # Schema
    "SCHEMA_VERSION",
    "SESSIONS_TABLE",
    "MESSAGES_TABLE",
    "FTS5_SCHEMA",
    "SEARCH_HISTORY_TABLE",
    "QUERY_CACHE_TABLE",
    "INDEX_STATUS_TABLE",
    "TRIGGERS",
    "INIT_SCRIPT",
    "REBUILD_SCRIPT",
    "OPTIMIZE_SCRIPT",
]
