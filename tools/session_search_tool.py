"""
MimirAether Session Search Tool - 会话历史搜索

学习自Hermes session_search_tool.py设计。

核心功能：
- 全文搜索：默认 SQLite LIKE；`SESSION_SEARCH_BACKEND=fts5|hybrid` 使用 `fts5_search.db`
- 会话分组和截断
- 摘要生成
"""

from __future__ import annotations

import json
import logging
import os
import re
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union, Tuple

logger = logging.getLogger(__name__)

# ============================================================================
# 常量
# ============================================================================

MAX_SESSION_CHARS = 100_000
MAX_SUMMARY_TOKENS = 10000


def _search_terms(query: str) -> List[str]:
    """Split query into terms; multi-word queries require all terms to match."""
    q = query.strip()
    if not q:
        return []
    parts = [p for p in q.split() if p]
    return parts if len(parts) > 1 else [q]


def _like_and_clause(column: str, terms: List[str]) -> Tuple[str, List[str]]:
    clause = " AND ".join(f"{column} LIKE ?" for _ in terms)
    params = [f"%{t}%" for t in terms]
    return clause, params


# ============================================================================
# 时间戳格式化
# ============================================================================

def _format_timestamp(ts: Union[int, float, str, None]) -> str:
    """Convert a Unix timestamp or ISO string to a human-readable date."""
    if ts is None:
        return "unknown"
    try:
        if isinstance(ts, (int, float)):
            dt = datetime.fromtimestamp(ts)
            return dt.strftime("%B %d, %Y at %I:%M %p")
        if isinstance(ts, str):
            if ts.replace(".", "").replace("-", "").isdigit():
                dt = datetime.fromtimestamp(float(ts))
                return dt.strftime("%B %d, %Y at %I:%M %p")
            return ts
    except (ValueError, OSError, OverflowError) as e:
        logger.debug("Failed to format timestamp %s: %s", ts, e)
    except Exception as e:
        logger.debug("Unexpected error formatting timestamp %s: %s", ts, e)
    return str(ts)


# ============================================================================
# 会话格式化
# ============================================================================

def _format_conversation(messages: List[Dict[str, Any]]) -> str:
    """Format session messages into a readable transcript."""
    parts = []
    for msg in messages:
        role = msg.get("role", "unknown").upper()
        content = msg.get("content") or ""
        tool_name = msg.get("tool_name")

        if role == "TOOL" and tool_name:
            if len(content) > 500:
                content = content[:250] + "\n...[truncated]...\n" + content[-250:]
            parts.append(f"[TOOL:{tool_name}]: {content}")
        elif role == "ASSISTANT":
            tool_calls = msg.get("tool_calls")
            if tool_calls and isinstance(tool_calls, list):
                tc_names = []
                for tc in tool_calls:
                    if isinstance(tc, dict):
                        name = tc.get("name") or tc.get("function", {}).get("name", "?")
                        tc_names.append(name)
                if tc_names:
                    parts.append(f"[ASSISTANT]: [Called: {', '.join(tc_names)}]")
                if content:
                    parts.append(f"[ASSISTANT]: {content}")
            else:
                parts.append(f"[ASSISTANT]: {content}")
        else:
            parts.append(f"[{role}]: {content}")

    return "\n\n".join(parts)


# ============================================================================
# 截断策略
# ============================================================================

def _truncate_around_matches(
    full_text: str, query: str, max_chars: int = MAX_SESSION_CHARS
) -> str:
    """
    Truncate a conversation to *max_chars*, maximizing coverage of query matches.
    """
    if len(full_text) <= max_chars:
        return full_text

    text_lower = full_text.lower()
    query_lower = query.lower().strip()
    match_positions: list[int] = []

    # 1. Full phrase search
    phrase_pat = re.compile(re.escape(query_lower))
    match_positions = [m.start() for m in phrase_pat.finditer(text_lower)]

    # 2. Proximity co-occurrence
    if not match_positions:
        terms = query_lower.split()
        if len(terms) > 1:
            term_positions: dict[str, list[int]] = {}
            for t in terms:
                term_positions[t] = [
                    m.start() for m in re.finditer(re.escape(t), text_lower)
                ]
            if term_positions:
                rarest = min(terms, key=lambda t: len(term_positions.get(t, [])))
                for pos in term_positions.get(rarest, []):
                    if all(
                        any(abs(p - pos) < 200 for p in term_positions.get(t, []))
                        for t in terms
                        if t != rarest
                    ):
                        match_positions.append(pos)

    # 3. Individual term positions
    if not match_positions:
        terms = query_lower.split()
        for t in terms:
            for m in re.finditer(re.escape(t), text_lower):
                match_positions.append(m.start())

    if not match_positions:
        truncated = full_text[:max_chars]
        suffix = "\n\n...[later conversation truncated]..." if max_chars < len(full_text) else ""
        return truncated + suffix

    match_positions.sort()

    best_start = 0
    best_count = 0
    for candidate in match_positions:
        ws = max(0, candidate - max_chars // 4)
        we = ws + max_chars
        if we > len(full_text):
            ws = max(0, len(full_text) - max_chars)
            we = len(full_text)
        count = sum(1 for p in match_positions if ws <= p < we)
        if count > best_count:
            best_count = count
            best_start = ws

    start = best_start
    end = min(len(full_text), start + max_chars)

    truncated = full_text[start:end]
    prefix = "...[earlier conversation truncated]...\n\n" if start > 0 else ""
    suffix = "\n\n...[later conversation truncated]..." if end < len(full_text) else ""
    return prefix + truncated + suffix


# ============================================================================
# 简单摘要生成（不依赖LLM）
# ============================================================================

def simple_summarize(conversation_text: str, query: str) -> str:
    """
    简单摘要：提取与查询相关的内容片段

    当没有LLM可用时使用。
    """
    lines = conversation_text.split("\n")
    relevant_lines = []

    query_terms = query.lower().split()

    for line in lines:
        line_lower = line.lower()
        if any(term in line_lower for term in query_terms):
            relevant_lines.append(line)

    if not relevant_lines:
        # 没有匹配，返回开头部分
        return conversation_text[:500] + "..."

    # 合并相关行
    summary_parts = []
    current_block = []
    for line in relevant_lines[:20]:  # 最多20行
        if line.startswith("[") and not current_block:
            summary_parts.append(line)
        elif current_block and line.startswith("[ASSISTANT]"):
            summary_parts.append("\n".join(current_block))
            summary_parts.append(line)
            current_block = []
        else:
            current_block.append(line)

    if current_block:
        summary_parts.append("\n".join(current_block))

    return "\n\n".join(summary_parts[:30])


# ============================================================================
# 会话数据库接口
# ============================================================================

class SessionSearchDB:
    """
    会话搜索数据库接口

    管理会话消息的存储和搜索
    """

    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            from mimir_constants import get_mimir_session_search_db_path

            db_path = str(get_mimir_session_search_db_path())
        self.db_path = db_path
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        """确保数据库schema存在"""
        if not Path(self.db_path).exists():
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

        conn = sqlite3.connect(self.db_path)
        try:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    source TEXT,
                    started_at REAL,
                    ended_at REAL,
                    title TEXT,
                    message_count INTEGER DEFAULT 0
                );

                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT,
                    role TEXT,
                    content TEXT,
                    tool_name TEXT,
                    timestamp REAL,
                    FOREIGN KEY (session_id) REFERENCES sessions(session_id)
                );

                CREATE INDEX IF NOT EXISTS idx_messages_session
                    ON messages(session_id);
            """)
        finally:
            conn.close()

    def search(
        self,
        query: str,
        limit: int = 5,
        session_limit: int = 3,
    ) -> List[Dict[str, Any]]:
        """
        搜索会话消息

        Args:
            query: 搜索查询
            limit: 最多返回的消息数
            session_limit: 最多返回的唯一会话数

        Returns:
            搜索结果列表
        """
        conn = sqlite3.connect(self.db_path)
        try:
            terms = _search_terms(query)
            if not terms:
                return []

            where_clause, term_params = _like_and_clause("m.content", terms)
            cursor = conn.execute(
                f"""
                SELECT DISTINCT m.session_id, s.source, s.started_at, s.title
                FROM messages m
                JOIN sessions s ON m.session_id = s.session_id
                WHERE {where_clause}
                ORDER BY s.started_at DESC
                LIMIT ?
                """,
                (*term_params, session_limit),
            )

            results = []
            for row in cursor.fetchall():
                session_id, source, started_at, title = row

                msg_where, msg_params = _like_and_clause("content", terms)
                msg_cursor = conn.execute(
                    f"""
                    SELECT role, content, tool_name, timestamp
                    FROM messages
                    WHERE session_id = ? AND {msg_where}
                    ORDER BY timestamp
                    LIMIT ?
                    """,
                    (session_id, *msg_params, limit),
                )

                messages = []
                for msg_row in msg_cursor.fetchall():
                    role, content, tool_name, timestamp = msg_row
                    if content:
                        messages.append({
                            "role": role,
                            "content": content[:500],  # 截断
                            "tool_name": tool_name,
                            "timestamp": timestamp,
                        })

                if messages:
                    results.append({
                        "session_id": session_id,
                        "source": source or "unknown",
                        "started_at": _format_timestamp(started_at),
                        "title": title or "Untitled",
                        "messages": messages,
                    })

            return results
        finally:
            conn.close()

    def add_session(
        self,
        session_id: str,
        source: str = "cli",
        title: str = "",
    ) -> None:
        """添加新会话"""
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute("""
                INSERT OR REPLACE INTO sessions (session_id, source, started_at, title)
                VALUES (?, ?, ?, ?)
            """, (session_id, source, datetime.now().timestamp(), title))
            conn.commit()
        finally:
            conn.close()

    def clear_session_messages(self, session_id: str) -> None:
        """Remove indexed messages for a session (session row kept for metadata)."""
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
            conn.execute(
                "UPDATE sessions SET message_count = 0 WHERE session_id = ?",
                (session_id,),
            )
            conn.commit()
        finally:
            conn.close()

    def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        tool_name: Optional[str] = None,
    ) -> None:
        """添加消息到会话"""
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute("""
                INSERT INTO messages (session_id, role, content, tool_name, timestamp)
                VALUES (?, ?, ?, ?, ?)
            """, (session_id, role, content, tool_name, datetime.now().timestamp()))

            conn.execute("""
                UPDATE sessions
                SET message_count = message_count + 1
                WHERE session_id = ?
            """, (session_id,))
            conn.commit()
        finally:
            conn.close()


# ============================================================================
# Backend selection (P1-M04)
# ============================================================================

def get_session_search_backend() -> str:
    """``like`` (default), ``fts5``, or ``hybrid`` (FTS5 then LIKE if empty)."""
    raw = os.environ.get("SESSION_SEARCH_BACKEND", "like").strip().lower()
    if raw in ("fts5", "hybrid"):
        return raw
    return "like"


def _default_fts5_db_path() -> str:
    from mimir_constants import get_mimir_data_dir

    return os.environ.get(
        "OPENCLAW_FTS5_DB",
        str(get_mimir_data_dir() / "fts5_search.db"),
    )


def _session_search_via_fts5(
    query: str,
    *,
    fts_db_path: str,
    limit: int,
    session_limit: int,
) -> List[Dict[str, Any]]:
    from tools.fts5_search.engine import FTS5SearchEngine, SearchOptions

    if not Path(fts_db_path).exists():
        return []

    engine = FTS5SearchEngine(fts_db_path)
    try:
        resp = engine.search(
            SearchOptions(
                query=query,
                limit=session_limit,
                use_cache=False,
                highlight=False,
            )
        )
    finally:
        engine.close()

    processed: List[Dict[str, Any]] = []
    for sr in resp.results[:session_limit]:
        messages: List[Dict[str, Any]] = []
        for seg in sr.matches[:limit]:
            if not seg.content:
                continue
            messages.append(
                {
                    "role": seg.role or "unknown",
                    "content": (seg.content or "")[:500],
                    "tool_name": None,
                    "timestamp": seg.created_at,
                }
            )
        if not messages:
            continue

        conversation = _format_conversation(messages)
        truncated = _truncate_around_matches(conversation, query)
        summary = simple_summarize(truncated, query)
        processed.append(
            {
                "session_id": sr.session_id,
                "source": sr.source or "unknown",
                "started_at": _format_timestamp(sr.created_at),
                "title": sr.session_title or "Untitled",
                "summary": summary,
                "message_count": len(messages),
            }
        )
    return processed


# ============================================================================
# 主搜索函数
# ============================================================================

def session_search(
    query: str,
    db_path: Optional[str] = None,
    limit: int = 5,
    session_limit: int = 3,
    use_llm: bool = False,
) -> List[Dict[str, Any]]:
    """
    搜索会话历史

    Args:
        query: 搜索查询
        db_path: 数据库路径
        limit: 每个会话最多消息数
        session_limit: 最多会话数
        use_llm: 是否使用LLM生成摘要

    Returns:
        搜索结果列表
    """
    backend = get_session_search_backend()
    fts_path = _default_fts5_db_path()

    if backend in ("fts5", "hybrid") and Path(fts_path).exists():
        fts_results = _session_search_via_fts5(
            query,
            fts_db_path=fts_path,
            limit=limit,
            session_limit=session_limit,
        )
        if fts_results or backend == "fts5":
            return fts_results

    db = SessionSearchDB(db_path)
    results = db.search(query, limit=limit, session_limit=session_limit)

    # 处理结果
    processed = []
    for result in results:
        messages = result.get("messages", [])
        if not messages:
            continue

        # 格式化会话
        conversation = _format_conversation(messages)

        # 截断到匹配区域
        truncated = _truncate_around_matches(conversation, query)

        # 生成摘要
        if use_llm:
            summary = simple_summarize(truncated, query)  # 暂时用简单版本
        else:
            summary = simple_summarize(truncated, query)

        processed.append({
            "session_id": result["session_id"],
            "source": result["source"],
            "started_at": result["started_at"],
            "title": result["title"],
            "summary": summary,
            "message_count": len(messages),
        })

    return processed


# ============================================================================
# Registry (Hermes-parity tool name ``session_search``)
# ============================================================================

from tools.registry import registry, tool_error, tool_result


def check_session_search_requirements() -> bool:
    try:
        from mimir_constants import get_mimir_home

        return get_mimir_home().is_dir()
    except Exception:
        return True


SESSION_SEARCH_SCHEMA = {
    "name": "session_search",
    "description": (
        "Search stored session messages by keyword (local SQLite index). "
        "Set SESSION_SEARCH_BACKEND=fts5 or hybrid for FTS5 on fts5_search.db. "
        "Use when the user refers to past work across sessions."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "Keywords to match in message content.",
            },
            "db_path": {
                "type": "string",
                "description": "Optional override path to sessions SQLite DB.",
            },
            "limit": {
                "type": "integer",
                "description": "Max messages sampled per session (default 5).",
            },
            "session_limit": {
                "type": "integer",
                "description": "Max sessions to return (default 3).",
            },
        },
        "required": [],
    },
}


def _session_search_handler(args, **kw):
    q = args.get("query")
    if q is None:
        q = ""
    if not isinstance(q, str):
        return tool_error("query must be a string", success=False)
    try:
        lim = int(args.get("limit", 5))
        sess_lim = int(args.get("session_limit", 3))
    except (TypeError, ValueError):
        return tool_error("limit and session_limit must be integers", success=False)
    db_path = args.get("db_path")
    if db_path is not None and not isinstance(db_path, str):
        return tool_error("db_path must be a string", success=False)
    results = session_search(
        query=q,
        db_path=db_path,
        limit=max(1, min(lim, 50)),
        session_limit=max(1, min(sess_lim, 20)),
    )
    return tool_result(success=True, query=q, results=results, count=len(results))


registry.register(
    name="session_search",
    toolset="session_search",
    schema=SESSION_SEARCH_SCHEMA,
    handler=lambda args, **kw: _session_search_handler(args, **kw),
    check_fn=check_session_search_requirements,
    emoji="🔍",
)


# ============================================================================
# 测试
# ============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("Session Search Tool 测试")
    print("=" * 60)

    import tempfile

    # 测试1: _format_timestamp
    print("\n[测试1] _format_timestamp")
    ts = datetime.now().timestamp()
    formatted = _format_timestamp(ts)
    assert "at" in formatted
    print(f"  格式化: {formatted}")
    print("  ✅ 通过")

    # 测试2: _format_conversation
    print("\n[测试2] _format_conversation")
    messages = [
        {"role": "user", "content": "Hello"},
        {"role": "assistant", "content": "Hi there!"},
        {"role": "tool", "tool_name": "search", "content": "Result 1"},
    ]
    formatted = _format_conversation(messages)
    assert "USER" in formatted
    assert "ASSISTANT" in formatted
    assert "TOOL:search" in formatted
    print(f"  格式化: {formatted[:100]}...")
    print("  ✅ 通过")

    # 测试3: _truncate_around_matches
    print("\n[测试3] _truncate_around_matches")
    long_text = "A" * 200 + " python is great " + "B" * 200
    truncated = _truncate_around_matches(long_text, "python", max_chars=100)
    assert "python" in truncated
    assert len(truncated) <= 200  # 包含前缀/后缀
    print(f"  截断后: {truncated[:80]}...")
    print("  ✅ 通过")

    # 测试4: SessionSearchDB
    print("\n[测试4] SessionSearchDB")
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        db = SessionSearchDB(db_path)

        # 添加会话
        db.add_session("test-1", "cli", "Test Session")

        # 添加消息
        db.add_message("test-1", "user", "Hello world")
        db.add_message("test-1", "assistant", "Hi there!")
        db.add_message("test-1", "user", "Tell me about Python")

        # 搜索
        results = db.search("Python", session_limit=5)
        assert len(results) >= 1
        print(f"  搜索到{len(results)}个会话")
        print("  ✅ 通过")

    # 测试5: simple_summarize
    print("\n[测试5] simple_summarize")
    text = "[USER]: Tell me about Python\n[ASSISTANT]: Python is a programming language"
    summary = simple_summarize(text, "Python")
    assert "Python" in summary
    print(f"  摘要: {summary[:80]}...")
    print("  ✅ 通过")

    # 测试6: session_search
    print("\n[测试6] session_search")
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = os.path.join(tmpdir, "test.db")
        db = SessionSearchDB(db_path)
        db.add_session("sess-1", "cli", "Python Help")
        db.add_message("sess-1", "user", "How to use Python dictionaries?")
        db.add_message("sess-1", "assistant", "Dictionaries in Python are...")

        results = session_search("Python", db_path=db_path, session_limit=3)
        assert len(results) >= 1
        assert "summary" in results[0]
        print(f"  结果数: {len(results)}, 摘要长度: {len(results[0]['summary'])}")
        print("  ✅ 通过")

    print("\n" + "=" * 60)
    print("所有测试通过!")
    print("=" * 60)