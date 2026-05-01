"""
MimirAether FTS5 Search Engine - 核心搜索引擎实现

核心功能：
- FTS5全文索引管理
- BM25相关性评分
- 跨会话搜索
- 结果高亮和分页

版本: 1.0.0
日期: 2026-04-20
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
import re
import sqlite3
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Callable

logger = logging.getLogger(__name__)

# ============================================================================
# 配置常量
# ============================================================================

# BM25参数
BM25_K1 = 1.2  # 词频饱和参数
BM25_B = 0.75  # 文档长度归一化参数

# 缓存配置
CACHE_TTL_SECONDS = 3600  # 1小时
CACHE_MAX_SIZE = 1000

# 批量索引配置
BATCH_SIZE = 100

# 搜索配置
DEFAULT_LIMIT = 10
MAX_LIMIT = 100

# ============================================================================
# 数据类定义
# ============================================================================

@dataclass
class SearchOptions:
    """搜索选项"""
    query: str
    session_ids: Optional[List[str]] = None
    limit: int = DEFAULT_LIMIT
    offset: int = 0
    sort_by: str = "relevance"  # relevance | created | session
    highlight: bool = True
    use_cache: bool = True
    include_metadata: bool = False

@dataclass
class MatchSegment:
    """匹配片段"""
    rowid: int
    session_id: str
    role: str
    content: str
    highlight: str = ""
    score: float = 0.0
    created_at: float = 0.0

@dataclass
class SearchResult:
    """搜索结果"""
    session_id: str
    session_title: str = ""
    score: float = 0.0
    matches: List[MatchSegment] = field(default_factory=list)
    created_at: float = 0.0
    message_count: int = 0
    source: str = "cli"

@dataclass 
class SearchResponse:
    """搜索响应"""
    query: str
    results: List[SearchResult]
    total_matches: int
    took_ms: float
    cached: bool = False
    offset: int = 0
    limit: int = DEFAULT_LIMIT

# ============================================================================
# BM25评分器
# ============================================================================

class BM25Scorer:
    """BM25相关性评分器
    
    BM25 (Best Matching 25) 是一种经典的信息检索评分函数，
    用于评估文档与查询的相关性。
    """
    
    def __init__(self, k1: float = BM25_K1, b: float = BM25_B):
        self.k1 = k1
        self.b = b
        self._avgdl = 0.0
        self._doc_lengths: Dict[int, int] = {}
        self._doc_freqs: Dict[str, int] = {}
        self._doc_term_counts: Dict[int, Dict[str, int]] = {}
        self._N = 0  # 文档总数
    
    def index(self, doc_id: int, terms: List[str], doc_length: int) -> None:
        """索引文档
        
        Args:
            doc_id: 文档ID
            terms: 文档分词列表
            doc_length: 文档长度（词数）
        """
        self._doc_lengths[doc_id] = doc_length
        self._N += 1
        self._avgdl = (self._avgdl * (self._N - 1) + doc_length) / self._N
        
        # 统计词频和文档频率
        term_counts: Dict[str, int] = {}
        for term in terms:
            term_counts[term] = term_counts.get(term, 0) + 1
        
        # 保存文档内的词频
        self._doc_term_counts[doc_id] = term_counts
        
        # 统计文档频率（多少文档包含该词）
        for term in term_counts:
            self._doc_freqs[term] = self._doc_freqs.get(term, 0) + 1
    
    def score(self, doc_id: int, query_terms: List[str]) -> float:
        """计算文档的BM25评分
        
        Args:
            doc_id: 文档ID
            query_terms: 查询分词列表
            
        Returns:
            BM25评分
        """
        if doc_id not in self._doc_lengths:
            return 0.0
        
        doc_len = self._doc_lengths[doc_id]
        score = 0.0
        
        # 获取该文档的词频
        doc_term_counts = self._doc_term_counts.get(doc_id, {})
        
        for term in query_terms:
            df = self._doc_freqs.get(term, 0)
            if df == 0:
                continue
            
            # IDF计算
            idf = math.log((self._N - df + 0.5) / (df + 0.5) + 1)
            
            # TF计算
            tf = doc_term_counts.get(term, 0)
            if tf == 0:
                continue
            
            # BM25公式
            numerator = tf * (self.k1 + 1)
            denominator = tf + self.k1 * (1 - self.b + self.b * doc_len / max(self._avgdl, 1))
            
            score += idf * numerator / denominator
        
        return score
    
    def get_idf(self, term: str) -> float:
        """获取词的IDF值"""
        df = self._doc_freqs.get(term, 0)
        if df == 0:
            return 0.0
        return math.log((self._N - df + 0.5) / (df + 0.5) + 1)

# ============================================================================
# FTS5搜索引擎
# ============================================================================

class FTS5SearchEngine:
    """
    FTS5全文搜索引擎
    
    提供高性能的跨会话全文搜索能力。
    支持：
    - FTS5全文索引
    - BM25相关性评分
    - 结果高亮
    - 查询缓存
    - 增量索引
    """
    
    def __init__(
        self,
        db_path: Optional[str] = None,
        wal_mode: bool = True,
        cache_ttl: int = CACHE_TTL_SECONDS,
    ):
        """初始化搜索引擎
        
        Args:
            db_path: 数据库路径
            wal_mode: 是否启用WAL模式
            cache_ttl: 缓存生存时间（秒）
        """
        if db_path is None:
            db_path = str(Path.home() / ".openclaw" / "fts5_search.db")
        
        self.db_path = db_path
        self.cache_ttl = cache_ttl
        self._bm25 = BM25Scorer()
        self._conn: Optional[sqlite3.Connection] = None
        self._init_database(wal_mode)
    
    def _init_database(self, wal_mode: bool) -> None:
        """初始化数据库"""
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        
        self._conn = sqlite3.connect(
            self.db_path,
            timeout=30.0,
            isolation_level=None,
        )
        
        # 配置SQLite
        self._conn.execute("PRAGMA journal_mode=WAL" if wal_mode else "PRAGMA journal_mode=DELETE")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._conn.execute("PRAGMA cache_size=10000")
        self._conn.execute("PRAGMA temp_store=MEMORY")
        self._conn.execute("PRAGMA foreign_keys=ON")
        
        # 初始化schema
        self._init_schema()
    
    def _init_schema(self) -> None:
        """初始化数据库schema"""
        from .schema import INIT_SCRIPT, TRIGGERS
        
        # 执行初始化脚本
        self._conn.executescript(INIT_SCRIPT)
        
        # 创建FTS5虚拟表
        self._create_fts5_table()
        
        # 创建触发器
        for trigger_name, trigger_sql in TRIGGERS.items():
            try:
                self._conn.executescript(trigger_sql)
            except sqlite3.OperationalError as e:
                if "already exists" not in str(e):
                    raise
                logger.debug("Trigger %s already exists", trigger_name)
    
    def _create_fts5_table(self) -> None:
        """创建FTS5虚拟表"""
        from .schema import FTS5_SCHEMA
        
        # 检查FTS5表是否存在
        cursor = self._conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='messages_fts'"
        )
        if cursor.fetchone():
            return  # 已存在
        
        # 分离单个CREATE语句并执行
        for statement in FTS5_SCHEMA.split(';'):
            statement = statement.strip()
            if statement:
                self._conn.execute(statement)
    
    def _ensure_session(self, session_id: str, source: str = "cli", title: str = "") -> None:
        """确保会话存在"""
        now = datetime.now().timestamp()
        self._conn.execute("""
            INSERT OR IGNORE INTO sessions (session_id, source, title, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
        """, (session_id, source, title, now, now))
    
    def index_message(
        self,
        session_id: str,
        role: str,
        content: str,
        metadata: Optional[Dict] = None,
        content_hash: Optional[str] = None,
    ) -> int:
        """索引单条消息
        
        Args:
            session_id: 会话ID
            role: 角色 (user/assistant/tool)
            content: 消息内容
            metadata: 额外元数据
            content_hash: 内容哈希（用于去重）
            
        Returns:
            消息ID
        """
        if not content or not content.strip():
            return -1
        
        # 计算内容哈希
        if content_hash is None:
            content_hash = hashlib.sha256(content.encode()).hexdigest()[:32]
        
        # 确保会话存在
        self._ensure_session(session_id)
        
        now = datetime.now().timestamp()
        
        # 插入消息
        cursor = self._conn.execute("""
            INSERT INTO messages (session_id, role, content, content_hash, created_at, metadata)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (session_id, role, content, content_hash, now, json.dumps(metadata) if metadata else None))
        
        msg_id = cursor.lastrowid
        
        # 索引到FTS5 (使用标准FTS5插入)
        self._conn.execute("""
            INSERT INTO messages_fts(rowid, content) VALUES (?, ?)
        """, (msg_id, content))
        
        # 更新会话消息数
        self._conn.execute("""
            UPDATE sessions 
            SET message_count = message_count + 1, updated_at = ?
            WHERE session_id = ?
        """, (now, session_id))
        
        return msg_id
    
    def index_batch(self, messages: List[Dict[str, Any]]) -> int:
        """批量索引消息
        
        Args:
            messages: 消息列表，每条消息包含session_id, role, content
            
        Returns:
            索引的消息数
        """
        if not messages:
            return 0
        
        indexed = 0
        now = datetime.now().timestamp()
        
        # 收集所有会话ID
        session_ids = set(m.get("session_id") for m in messages if m.get("session_id"))
        
        # 确保所有会话存在
        for session_id in session_ids:
            self._ensure_session(session_id)
        
        # 批量插入
        self._conn.execute("BEGIN TRANSACTION")
        try:
            for msg in messages:
                session_id = msg.get("session_id")
                role = msg.get("role", "user")
                content = msg.get("content", "")
                metadata = msg.get("metadata")
                
                if not content or not session_id:
                    continue
                
                content_hash = msg.get("content_hash") or hashlib.sha256(content.encode()).hexdigest()[:32]
                
                cursor = self._conn.execute("""
                    INSERT INTO messages (session_id, role, content, content_hash, created_at, metadata)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (session_id, role, content, content_hash, msg.get("created_at", now), 
                      json.dumps(metadata) if metadata else None))
                
                msg_id = cursor.lastrowid
                
                # 索引到FTS5 (使用标准FTS5插入)
                self._conn.execute("""
                    INSERT INTO messages_fts(rowid, content) VALUES (?, ?)
                """, (msg_id, content))
                
                indexed += 1
            
            # 批量更新会话消息数
            for session_id in session_ids:
                count = sum(1 for m in messages if m.get("session_id") == session_id)
                self._conn.execute("""
                    UPDATE sessions 
                    SET message_count = message_count + ?, updated_at = ?
                    WHERE session_id = ?
                """, (count, now, session_id))
            
            self._conn.execute("COMMIT")
        except Exception as e:
            self._conn.execute("ROLLBACK")
            raise e
        
        return indexed
    
    def search(self, options: SearchOptions) -> SearchResponse:
        """执行搜索
        
        Args:
            options: 搜索选项
            
        Returns:
            搜索响应
        """
        start_time = time.time()
        
        # 检查缓存
        cached = False
        if options.use_cache:
            cached_result = self._get_cached(options)
            if cached_result is not None:
                cached_result.cached = True
                return cached_result
        
        # 构建查询
        query = self._prepare_query(options.query)
        
        # 执行FTS5搜索
        results = self._execute_fts_search(query, options)
        
        # 应用BM25评分
        results = self._score_results(results, options.query)
        
        # 排序
        results = self._sort_results(results, options.sort_by)
        
        # 高亮
        if options.highlight:
            results = self._highlight_results(results, options.query)
        
        # 分页
        total = len(results)
        results = results[options.offset:options.offset + options.limit]
        
        took_ms = (time.time() - start_time) * 1000
        
        # 缓存结果
        if options.use_cache and total > 0:
            self._cache_results(options, SearchResponse(
                query=options.query,
                results=results,
                total_matches=total,
                took_ms=took_ms,
                offset=options.offset,
                limit=options.limit,
            ))
        
        # 记录搜索历史
        self._record_search(options.query, total, took_ms)
        
        return SearchResponse(
            query=options.query,
            results=results,
            total_matches=total,
            took_ms=took_ms,
            offset=options.offset,
            limit=options.limit,
        )
    
    def _prepare_query(self, query: str) -> str:
        """准备FTS5查询"""
        # 转义特殊字符
        query = query.replace('"', '""')
        
        # 处理布尔操作符
        query = query.strip()
        
        # 如果包含空格且没有操作符，转换为AND查询
        if ' ' in query and not any(op in query.upper() for op in ['AND', 'OR', 'NOT']):
            terms = query.split()
            query = ' AND '.join(f'"{t}"' for t in terms if t)
        
        return query
    
    def _execute_fts_search(
        self,
        query: str,
        options: SearchOptions,
    ) -> List[SearchResult]:
        """执行FTS5搜索"""
        results: Dict[str, SearchResult] = {}
        
        # 构建SQL
        sql = """
            SELECT 
                m.session_id,
                m.id as rowid,
                m.role,
                m.content,
                m.created_at,
                s.title,
                s.source,
                s.created_at as session_created_at,
                bm25(messages_fts)
            FROM messages_fts
            JOIN messages m ON messages_fts.rowid = m.id
            JOIN sessions s ON m.session_id = s.session_id
            WHERE messages_fts MATCH ?
        """
        params: List[Any] = [query]
        
        if options.session_ids:
            placeholders = ','.join('?' * len(options.session_ids))
            sql += f" AND m.session_id IN ({placeholders})"
            params.extend(options.session_ids)
        
        sql += " ORDER BY bm25(messages_fts) DESC LIMIT 1000"
        
        try:
            cursor = self._conn.execute(sql, params)
            for row in cursor.fetchall():
                (session_id, rowid, role, content, created_at, 
                 title, source, session_created_at, bm25_score) = row
                
                if session_id not in results:
                    results[session_id] = SearchResult(
                        session_id=session_id,
                        session_title=title or "",
                        score=0.0,
                        created_at=session_created_at or 0,
                        source=source or "cli",
                    )
                
                # 添加匹配片段
                segment = MatchSegment(
                    rowid=rowid,
                    session_id=session_id,
                    role=role or "unknown",
                    content=content or "",
                    score=bm25_score or 0.0,
                    created_at=created_at or 0,
                )
                results[session_id].matches.append(segment)
                results[session_id].score += abs(bm25_score or 0)
        except sqlite3.OperationalError as e:
            logger.error("FTS5 search error: %s", e)
            # 降级为LIKE搜索
            return self._fallback_search(options)
        
        return list(results.values())
    
    def _fallback_search(self, options: SearchOptions) -> List[SearchResult]:
        """降级搜索（当FTS5不可用时）"""
        results: Dict[str, SearchResult] = {}
        
        sql = """
            SELECT 
                m.session_id,
                m.id,
                m.role,
                m.content,
                m.created_at,
                s.title,
                s.source,
                s.created_at
            FROM messages m
            JOIN sessions s ON m.session_id = s.session_id
            WHERE m.content LIKE ?
        """
        params: List[Any] = [f"%{options.query}%"]
        
        if options.session_ids:
            placeholders = ','.join('?' * len(options.session_ids))
            sql += f" AND m.session_id IN ({placeholders})"
            params.extend(options.session_ids)
        
        sql += " ORDER BY m.created_at DESC LIMIT 1000"
        
        cursor = self._conn.execute(sql, params)
        for row in cursor.fetchall():
            (session_id, rowid, role, content, created_at, 
             title, source, session_created_at) = row
            
            if session_id not in results:
                results[session_id] = SearchResult(
                    session_id=session_id,
                    session_title=title or "",
                    score=1.0,
                    created_at=session_created_at or 0,
                    source=source or "cli",
                )
            
            results[session_id].matches.append(MatchSegment(
                rowid=rowid,
                session_id=session_id,
                role=role or "unknown",
                content=content or "",
                score=1.0,
                created_at=created_at or 0,
            ))
        
        return list(results.values())
    
    def _score_results(
        self,
        results: List[SearchResult],
        query: str,
    ) -> List[SearchResult]:
        """对结果进行评分"""
        # BM25评分已在查询时计算
        # 这里可以添加额外的评分逻辑
        return results
    
    def _sort_results(
        self,
        results: List[SearchResult],
        sort_by: str,
    ) -> List[SearchResult]:
        """排序结果"""
        if sort_by == "relevance":
            return sorted(results, key=lambda r: r.score, reverse=True)
        elif sort_by == "created":
            return sorted(results, key=lambda r: r.created_at, reverse=True)
        elif sort_by == "session":
            return sorted(results, key=lambda r: r.session_id)
        return results
    
    def _highlight_results(
        self,
        results: List[SearchResult],
        query: str,
    ) -> List[SearchResult]:
        """高亮匹配片段"""
        # 提取查询词
        terms = query.lower().split()
        
        for result in results:
            for match in result.matches:
                highlighted = match.content
                
                # 简单的词高亮
                for term in terms:
                    if len(term) < 2:
                        continue
                    pattern = re.compile(re.escape(term), re.IGNORECASE)
                    highlighted = pattern.sub(
                        lambda m: f"**{m.group()}**",
                        highlighted
                    )
                
                # 截断到合理长度
                if len(highlighted) > 300:
                    # 找到第一个高亮位置
                    first_bold = highlighted.find("**")
                    if first_bold > 100:
                        start = max(0, first_bold - 50)
                        highlighted = "..." + highlighted[start:]
                    if len(highlighted) > 300:
                        highlighted = highlighted[:300] + "..."
                
                match.highlight = highlighted
        
        return results
    
    def _get_cached(self, options: SearchOptions) -> Optional[SearchResponse]:
        """获取缓存的搜索结果"""
        query_hash = self._compute_query_hash(options)
        
        cursor = self._conn.execute("""
            SELECT results_json, expires_at FROM query_cache
            WHERE query_hash = ?
        """, (query_hash,))
        
        row = cursor.fetchone()
        if row is None:
            return None
        
        results_json, expires_at = row
        
        # 检查是否过期
        if datetime.now().timestamp() > expires_at:
            self._conn.execute("DELETE FROM query_cache WHERE query_hash = ?", (query_hash,))
            return None
        
        # 更新访问统计
        self._conn.execute("""
            UPDATE query_cache 
            SET hit_count = hit_count + 1, last_accessed = ?
            WHERE query_hash = ?
        """, (datetime.now().timestamp(), query_hash))
        
        # 反序列化结果
        data = json.loads(results_json)
        return SearchResponse(
            query=data["query"],
            results=[SearchResult(**r) for r in data["results"]],
            total_matches=data["total_matches"],
            took_ms=data["took_ms"],
            cached=True,
            offset=data["offset"],
            limit=data["limit"],
        )
    
    def _cache_results(self, options: SearchOptions, response: SearchResponse) -> None:
        """缓存搜索结果"""
        query_hash = self._compute_query_hash(options)
        now = datetime.now().timestamp()
        
        # 准备缓存数据
        results_json = json.dumps({
            "query": response.query,
            "results": [
                {
                    **r.__dict__,
                    "matches": [m.__dict__ for m in r.matches],
                }
                for r in response.results
            ],
            "total_matches": response.total_matches,
            "took_ms": response.took_ms,
            "offset": response.offset,
            "limit": response.limit,
        })
        
        try:
            self._conn.execute("""
                INSERT OR REPLACE INTO query_cache 
                (query_hash, query_text, results_json, created_at, expires_at, hit_count, last_accessed)
                VALUES (?, ?, ?, ?, ?, 1, ?)
            """, (query_hash, options.query, results_json, now, now + self.cache_ttl, now))
            
            # 清理过期缓存
            self._conn.execute("DELETE FROM query_cache WHERE expires_at < ?", (now,))
            
            # 限制缓存大小
            cursor = self._conn.execute("SELECT COUNT(*) FROM query_cache")
            count = cursor.fetchone()[0]
            if count > CACHE_MAX_SIZE:
                self._conn.execute("""
                    DELETE FROM query_cache 
                    WHERE query_hash IN (
                        SELECT query_hash FROM query_cache 
                        ORDER BY hit_count ASC, last_accessed ASC 
                        LIMIT ?
                    )
                """, (count - CACHE_MAX_SIZE,))
        except sqlite3.Error as e:
            logger.warning("Failed to cache search results: %s", e)
    
    def _compute_query_hash(self, options: SearchOptions) -> str:
        """计算查询哈希"""
        key = f"{options.query}:{options.session_ids}:{options.offset}:{options.limit}"
        return hashlib.sha256(key.encode()).hexdigest()
    
    def _record_search(self, query: str, result_count: int, took_ms: float) -> None:
        """记录搜索历史"""
        now = datetime.now().timestamp()
        normalized = query.lower().strip()
        
        try:
            self._conn.execute("""
                INSERT INTO search_history (query, query_normalized, result_count, took_ms, searched_at)
                VALUES (?, ?, ?, ?, ?)
            """, (query, normalized, result_count, took_ms, now))
        except sqlite3.Error as e:
            logger.warning("Failed to record search history: %s", e)
    
    def rebuild_index(self) -> None:
        """重建FTS5索引"""
        logger.info("Rebuilding FTS5 index...")
        
        # 清空FTS5表
        self._conn.execute("DELETE FROM messages_fts")
        
        # 收集所有消息进行重新索引
        cursor = self._conn.execute("""
            SELECT id, content FROM messages ORDER BY id
        """)
        
        # 重新索引
        for row in cursor.fetchall():
            msg_id, content = row
            if content:
                self._conn.execute("""
                    INSERT INTO messages_fts(rowid, content) VALUES (?, ?)
                """, (msg_id, content))
        
        logger.info("FTS5 index rebuild complete")
    
    def optimize_index(self) -> None:
        """优化FTS5索引"""
        self._conn.execute("INSERT INTO messages_fts(messages_fts) VALUES('optimize')")
    
    def get_stats(self) -> Dict[str, Any]:
        """获取索引统计"""
        stats = {}
        
        # 会话数
        cursor = self._conn.execute("SELECT COUNT(*) FROM sessions")
        stats["session_count"] = cursor.fetchone()[0]
        
        # 消息数
        cursor = self._conn.execute("SELECT COUNT(*) FROM messages")
        stats["message_count"] = cursor.fetchone()[0]
        
        # 索引大小
        cursor = self._conn.execute("SELECT COUNT(*) FROM messages_fts")
        stats["fts_count"] = cursor.fetchone()[0]
        
        # 缓存命中率
        cursor = self._conn.execute("""
            SELECT SUM(hit_count), COUNT(*) FROM query_cache
        """)
        row = cursor.fetchone()
        stats["cache_hits"] = row[0] or 0
        stats["cache_entries"] = row[1] or 0
        
        # 搜索历史数
        cursor = self._conn.execute("SELECT COUNT(*) FROM search_history")
        stats["search_count"] = cursor.fetchone()[0]
        
        return stats
    
    def close(self) -> None:
        """关闭数据库连接"""
        if self._conn:
            self._conn.close()
            self._conn = None
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False


# ============================================================================
# 便捷函数
# ============================================================================

def create_engine(db_path: Optional[str] = None) -> FTS5SearchEngine:
    """创建FTS5搜索引擎实例"""
    return FTS5SearchEngine(db_path=db_path)


def quick_search(
    query: str,
    db_path: Optional[str] = None,
    limit: int = DEFAULT_LIMIT,
) -> SearchResponse:
    """快速搜索（便捷函数）"""
    engine = FTS5SearchEngine(db_path=db_path)
    try:
        return engine.search(SearchOptions(query=query, limit=limit))
    finally:
        engine.close()
