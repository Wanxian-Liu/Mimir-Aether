# MimirAether FTS5 跨会话搜索架构

> **版本**: 1.0.0  
> **日期**: 2026-04-20  
> **目标**: 实现高性能跨会话全文搜索能力

---

## 1. 设计目标

### 1.1 核心需求

| 需求 | 描述 | 优先级 |
|------|------|--------|
| FTS5全文搜索 | 利用SQLite FTS5实现高性能全文索引 | P0 |
| 跨会话检索 | 支持跨多个会话的语义搜索 | P0 |
| 语义相似度 | 支持基于关键词的相似度匹配 | P1 |
| 高性能查询 | 毫秒级响应复杂查询 | P0 |
| 可扩展性 | 支持未来嵌入向量搜索 | P2 |

### 1.2 性能指标

- **索引速度**: >1000条/秒
- **查询延迟**: <50ms (单会话), <200ms (跨会话)
- **内存占用**: <100MB (典型数据集)
- **可支持会话数**: 无限

---

## 2. 架构概览

```
┌─────────────────────────────────────────────────────────────┐
│                    FTS5 Search Architecture                  │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐ │
│  │ Session Index │    │   FTS5 Index │    │  Query Layer │ │
│  │   Manager     │───▶│   (SQLite)    │◀───│   (API)      │ │
│  └──────────────┘    └──────────────┘    └──────────────┘ │
│          │                  │                  │           │
│          ▼                  ▼                  ▼           │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐ │
│  │   Memory     │    │   BM25       │    │  Result      │ │
│  │   Bridge     │    │   Scorer     │    │  Aggregator  │ │
│  └──────────────┘    └──────────────┘    └──────────────┘ │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. 数据库Schema设计

### 3.1 主表结构

```sql
-- 会话元数据表
CREATE TABLE sessions (
    session_id TEXT PRIMARY KEY,
    source TEXT NOT NULL DEFAULT 'cli',
    title TEXT,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL,
    message_count INTEGER DEFAULT 0,
    is_archived INTEGER DEFAULT 0
);

-- 消息主表
CREATE TABLE messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    role TEXT NOT NULL,
    content TEXT,
    content_hash TEXT,
    token_count INTEGER,
    created_at REAL NOT NULL,
    metadata TEXT,  -- JSON格式存储额外信息
    FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE
);

-- 索引: 加速会话查询
CREATE INDEX idx_messages_session ON messages(session_id);
CREATE INDEX idx_messages_created ON messages(created_at);
```

### 3.2 FTS5虚拟表设计

```sql
-- FTS5全文索引表
CREATE VIRTUAL TABLE messages_fts USING fts5(
    content,
    content_rowid='rowid',
    tokenize='unicode61 remove_diacritics 2',
    pagestore='direct',
    schema='define=prefix=2'
);
```

> **注**: 为简化实现，未使用独立的 `messages_fts_content` 表和 `messages_fts_idx` 辅助表。原始消息存储在 `messages` 表中，通过 `rowid` 与FTS5虚拟表关联。

### 3.3 搜索历史与缓存

```sql
-- 搜索历史表
CREATE TABLE search_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    query TEXT NOT NULL,
    result_count INTEGER DEFAULT 0,
    took_ms REAL,
    searched_at REAL NOT NULL
);

-- 高频查询缓存
CREATE TABLE query_cache (
    query_hash TEXT PRIMARY KEY,
    query_text TEXT NOT NULL,
    results_json TEXT NOT NULL,
    created_at REAL NOT NULL,
    expires_at REAL NOT NULL,
    hit_count INTEGER DEFAULT 0
);
```

---

## 4. 核心模块设计

### 4.1 FTS5SearchEngine

**职责**: 管理FTS5索引的创建、维护和查询

**核心方法**:
- `index_message(session_id, role, content, ...)` - 索引单条消息
- `index_batch(messages)` - 批量索引消息（集成批量索引功能）
- `search(options)` - 执行搜索
- `rebuild_index()` - 重建整个索引
- `optimize_index()` - 优化索引
- `get_stats()` - 获取索引统计
- `close()` - 关闭数据库连接

### 4.2 BM25Scorer

**职责**: 计算BM25相关性评分

**公式**:
```
BM25(D, Q) = Σ IDF(qi) × (f(qi, D) × (k1 + 1)) / (f(qi, D) + k1 × (1 - b + b × |D|/avgdl))
```

**参数**:
- k1 = 1.2 (词频饱和参数)
- b = 0.75 (文档长度归一化参数)

### 4.3 Result Processing (内部实现)

**聚合功能由内部方法实现**:
- `_sort_results()` - 按相关性/时间/会话排序
- `_highlight_results()` - 高亮匹配片段
- `_score_results()` - BM25评分应用

---

## 5. 搜索API设计

### 5.1 搜索选项

```python
@dataclass
class SearchOptions:
    query: str                          # 搜索查询
    session_ids: Optional[List[str]]   # 限定会话范围
    limit: int = 10                    # 结果数量限制
    offset: int = 0                    # 结果偏移
    sort_by: str = "relevance"         # 排序方式 (relevance|created|session)
    highlight: bool = True             # 是否返回高亮片段
    use_cache: bool = True            # 是否使用缓存
```

### 5.2 搜索响应

```python
@dataclass
class SearchResult:
    session_id: str                    # 会话ID
    session_title: str                 # 会话标题
    score: float                       # 相关性评分
    matches: List[MatchSegment]        # 匹配片段
    created_at: float                  # 会话创建时间
    source: str = "cli"                # 数据源

@dataclass
class MatchSegment:
    rowid: int                         # 消息ID
    session_id: str                    # 会话ID
    role: str                          # 消息角色
    content: str                       # 原始内容
    highlight: str                     # 高亮后的内容
    score: float                       # 片段评分
    created_at: float                  # 消息创建时间

@dataclass
class SearchResponse:
    query: str                         # 原始查询
    results: List[SearchResult]        # 结果列表
    total_matches: int                 # 总匹配数
    took_ms: float                     # 耗时(毫秒)
    cached: bool                       # 是否命中缓存
    offset: int                        # 结果偏移
    limit: int                         # 结果限制
```

---

## 6. 高级特性

### 6.1 短语搜索

支持双引号精确匹配短语:
```sql
SELECT * FROM messages_fts WHERE messages_fts MATCH '"exact phrase"';
```

### 6.2 前缀搜索

支持*通配符前缀匹配:
```sql
SELECT * FROM messages_fts WHERE messages_fts MATCH 'python*';
```

### 6.3 布尔搜索

支持AND/OR/NOT操作:
```sql
SELECT * FROM messages_fts WHERE messages_fts MATCH 'python AND programming';
SELECT * FROM messages_fts WHERE messages_fts MATCH 'python OR ruby';
SELECT * FROM messages_fts WHERE messages_fts MATCH 'python NOT java';
```

### 6.4 语义相似度（扩展）

预留向量嵌入接口:
```python
async def semantic_search(self, query: str, embedding: np.ndarray):
    """基于向量相似度的搜索"""
    pass
```

---

## 7. 索引策略

### 7.1 增量索引

```python
# 只索引新增消息
last_indexed = get_last_indexed_timestamp()
new_messages = get_messages_since(last_indexed)
for msg in new_messages:
    index_message(msg)
update_last_indexed_timestamp()
```

### 7.2 批量索引

```python
# 批量提交减少I/O
BATCH_SIZE = 100
buffer = []
for msg in stream_messages():
    buffer.append(msg)
    if len(buffer) >= BATCH_SIZE:
        index_batch(buffer)
        buffer.clear()
if buffer:
    index_batch(buffer)
```

### 7.3 索引优化

```sql
-- 定期优化FTS索引
INSERT INTO messages_fts(messages_fts) VALUES('optimize');

-- 重建索引
INSERT INTO messages_fts(messages_fts) VALUES('rebuild');
```

---

## 8. 错误处理

| 错误类型 | 处理策略 |
|----------|----------|
| 数据库锁定 | 重试3次，指数退避 |
| 索引损坏 | 自动重建索引 |
| 查询超时 | 返回部分结果+警告 |
| 内存不足 | 分批处理+限制结果数 |

---

## 9. 监控指标

- `fts5_search_requests_total` - 搜索请求总数
- `fts5_search_latency_seconds` - 搜索延迟分布
- `fts5_index_messages_total` - 索引消息总数
- `fts5_cache_hit_ratio` - 缓存命中率
- `fts5_query_error_total` - 查询错误总数

---

## 10. 未来扩展

### 10.1 向量搜索集成

```python
# 预留接口
class VectorStore:
    def embed(self, texts: List[str]) -> np.ndarray: ...
    def search(self, query: str, k: int) -> List[SearchResult]: ...
```

### 10.2 分布式部署

- 主从复制
- 分片策略
- 负载均衡

---

## 附录

### A. FTS5配置参考

```python
TOKENIZER = 'unicode61 remove_diacritics 2'
# unicode61: Unicode-aware分词
# remove_diacritics: 去除变音符号
# 2: 最小词长度过滤
```

### B. 参考资料

- [SQLite FTS5文档](https://www.sqlite.org/fts5.html)
- [BM25算法](https://en.wikipedia.org/wiki/Okapi_BM25)
- [Whoosh BM25实现](https://whoosh.readthedocs.io/en/latest/bm25.html)
