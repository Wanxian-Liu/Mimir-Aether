"""
MimirAether FTS5 数据库Schema定义

版本: 1.0.0
日期: 2026-04-20
"""

from __future__ import annotations

# ============================================================================
# SQL Schema 版本号
# ============================================================================

SCHEMA_VERSION = 4

# ============================================================================
# 主表Schema
# ============================================================================

SESSIONS_TABLE = """
-- 会话元数据表
-- 存储会话的基本信息
CREATE TABLE IF NOT EXISTS sessions (
    session_id TEXT PRIMARY KEY,
    source TEXT NOT NULL DEFAULT 'cli',
    title TEXT,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL,
    message_count INTEGER DEFAULT 0,
    is_archived INTEGER DEFAULT 0,
    metadata TEXT
);
"""

SESSIONS_INDEXES = """
CREATE INDEX IF NOT EXISTS idx_sessions_created ON sessions(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_sessions_source ON sessions(source);
CREATE INDEX IF NOT EXISTS idx_sessions_archived ON sessions(is_archived);
"""

MESSAGES_TABLE = """
-- 消息主表
-- 存储所有会话消息
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    role TEXT NOT NULL,
    content TEXT,
    content_hash TEXT,
    token_count INTEGER,
    created_at REAL NOT NULL,
    metadata TEXT,
    FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE
);
"""

MESSAGES_INDEXES = """
CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id);
CREATE INDEX IF NOT EXISTS idx_messages_created ON messages(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_messages_role ON messages(role);
CREATE INDEX IF NOT EXISTS idx_messages_hash ON messages(content_hash);
"""

# ============================================================================
# FTS5虚拟表Schema
# ============================================================================

# 简化的FTS5配置，不使用外部内容表
FTS5_SCHEMA = """
-- FTS5全文索引虚拟表
-- 直接在FTS5表中存储内容，由FTS5自动管理
CREATE VIRTUAL TABLE IF NOT EXISTS messages_fts USING fts5(
    content,
    tokenize='unicode61 remove_diacritics 2',
    prefix='2'
);
"""

# ============================================================================
# 搜索历史与缓存Schema
# ============================================================================

SEARCH_HISTORY_TABLE = """
-- 搜索历史表
CREATE TABLE IF NOT EXISTS search_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    query TEXT NOT NULL,
    query_normalized TEXT NOT NULL,
    result_count INTEGER DEFAULT 0,
    took_ms REAL,
    searched_at REAL NOT NULL,
    session_id TEXT,
    user_id TEXT
);
"""

SEARCH_HISTORY_INDEXES = """
CREATE INDEX IF NOT EXISTS idx_search_history_query ON search_history(query_normalized);
CREATE INDEX IF NOT EXISTS idx_search_history_time ON search_history(searched_at DESC);
"""

QUERY_CACHE_TABLE = """
-- 高频查询缓存表
CREATE TABLE IF NOT EXISTS query_cache (
    query_hash TEXT PRIMARY KEY,
    query_text TEXT NOT NULL,
    results_json TEXT NOT NULL,
    created_at REAL NOT NULL,
    expires_at REAL NOT NULL,
    hit_count INTEGER DEFAULT 0,
    last_accessed REAL
);
"""

QUERY_CACHE_INDEXES = """
CREATE INDEX IF NOT EXISTS idx_cache_expires ON query_cache(expires_at);
CREATE INDEX IF NOT EXISTS idx_cache_hits ON query_cache(hit_count DESC);
"""

# ============================================================================
# Schema版本管理
# ============================================================================

INDEX_STATUS_TABLE = """
-- 索引状态跟踪表
CREATE TABLE IF NOT EXISTS index_status (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at REAL NOT NULL
);
"""

SCHEMA_VERSION_TABLE = """
-- Schema版本记录表
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    applied_at REAL NOT NULL,
    description TEXT
);
"""

# ============================================================================
# 完整初始化脚本
# ============================================================================

INIT_SCRIPT = f"""
PRAGMA journal_mode=WAL;
PRAGMA synchronous=NORMAL;
PRAGMA cache_size=10000;
PRAGMA temp_store=MEMORY;

{SESSIONS_TABLE}
{SESSIONS_INDEXES}
{MESSAGES_TABLE}
{MESSAGES_INDEXES}
{SEARCH_HISTORY_TABLE}
{SEARCH_HISTORY_INDEXES}
{QUERY_CACHE_TABLE}
{QUERY_CACHE_INDEXES}
{INDEX_STATUS_TABLE}
{SCHEMA_VERSION_TABLE}

INSERT OR REPLACE INTO schema_version (version, applied_at, description)
VALUES ({SCHEMA_VERSION}, unixepoch(), 'FTS5 cross-session search schema');
"""

# ============================================================================
# 触发器定义（用于自动同步FTS5）
# 注意：当前实现不使用触发器，采用手动索引方式
# ============================================================================

TRIGGERS = {}

# ============================================================================
# 重建索引脚本
# ============================================================================

REBUILD_SCRIPT = """
INSERT INTO messages_fts(messages_fts) VALUES('rebuild');
"""

# ============================================================================
# 优化索引脚本
# ============================================================================

OPTIMIZE_SCRIPT = """
INSERT INTO messages_fts(messages_fts) VALUES('optimize');
"""
