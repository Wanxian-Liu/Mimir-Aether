"""
MimirAether Insights Engine — 增强版

学习自Hermes Insights Engine设计，1:1参照改造。

核心改进：
- SessionDB直连：从SQLite直接查询sessions/messages表
- 完整成本估算：复用usage_pricing.py的CanonicalUsage/estimate_usage_cost
- 双源工具追踪：tool_name列 + tool_calls JSON
- 模型/平台分布：多维度使用分析
- 活动模式：星期/小时/连续天数统计
- Top Sessions：最长/最多消息/最多token/最多工具调用
- 双格式输出：终端(ASCII art) + 网关(消息格式)

Usage:
    from agent.insights import InsightsEngine
    engine = InsightsEngine(db)          # SQL模式（推荐）
    engine = InsightsEngine()            # 内存模式（向后兼容）
    report = engine.generate(days=30)
    print(engine.format_terminal(report))
"""

from __future__ import annotations

import json
import logging
import time
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, List, Literal, Optional, Tuple

from agent.usage_pricing import (
    CanonicalUsage,
    DEFAULT_PRICING as _UP_DEFAULT_PRICING,
    estimate_usage_cost,
    format_duration_compact,
    has_known_pricing,
)

logger = logging.getLogger(__name__)


# ============================================================================
# 类型别名
# ============================================================================

CostStatus = Literal["actual", "estimated", "included", "unknown"]


# ============================================================================
# 枚举
# ============================================================================

class MetricType(Enum):
    """指标类型"""
    TOKEN_INPUT = "token_input"
    TOKEN_OUTPUT = "token_output"
    TOKEN_CACHE_READ = "token_cache_read"
    TOKEN_CACHE_WRITE = "token_cache_write"
    COST = "cost"
    LATENCY = "latency"
    TOOL_CALL = "tool_call"
    ERROR = "error"


# ============================================================================
# 数据类
# ============================================================================

@dataclass
class UsageRecord:
    """使用记录"""
    timestamp: str
    metric: str
    value: float
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SessionInsights:
    """会话洞察"""
    session_id: str
    start_time: str
    end_time: Optional[str] = None
    total_messages: int = 0
    total_turns: int = 0
    total_tokens: int = 0
    total_cost: float = 0.0
    tool_calls: int = 0
    errors: int = 0
    platform: str = "unknown"


@dataclass
class InsightsReport:
    """洞察报告（兼容内存模式和SQL模式）"""
    # 元数据
    days: int = 30
    source_filter: Optional[str] = None
    empty: bool = True
    generated_at: float = 0.0

    # 核心统计
    total_sessions: int = 0
    total_messages: int = 0
    total_tool_calls: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_cache_read_tokens: int = 0
    total_cache_write_tokens: int = 0
    total_tokens: int = 0
    estimated_cost: float = 0.0
    actual_cost: float = 0.0
    total_hours: float = 0.0
    avg_session_duration: float = 0.0
    avg_messages_per_session: float = 0.0
    avg_tokens_per_session: float = 0.0

    # 消息分布
    user_messages: int = 0
    assistant_messages: int = 0
    tool_messages: int = 0

    # 日期范围
    date_range_start: Optional[float] = None
    date_range_end: Optional[float] = None

    # 模型统计
    models: List[Dict[str, Any]] = field(default_factory=list)
    models_with_pricing: List[str] = field(default_factory=list)
    models_without_pricing: List[str] = field(default_factory=list)
    unknown_cost_sessions: int = 0
    included_cost_sessions: int = 0

    # 平台分布
    platforms: List[Dict[str, Any]] = field(default_factory=list)

    # 工具排行
    tools: List[Dict[str, Any]] = field(default_factory=list)

    # 活动模式
    activity: Dict[str, Any] = field(default_factory=dict)

    # Top Sessions
    top_sessions: List[Dict[str, Any]] = field(default_factory=list)


# ============================================================================
# 辅助函数
# ============================================================================

def _has_known_pricing(
    model_name: str,
    provider: str = None,
    base_url: str = None,
) -> bool:
    """检查模型是否有已知定价"""
    return has_known_pricing(model_name, provider=provider, base_url=base_url)


def _estimate_cost_from_session(session: Dict[str, Any]) -> Tuple[float, str]:
    """从session行估算USD成本"""
    model = session.get("model") or ""
    usage = CanonicalUsage(
        input_tokens=session.get("input_tokens") or 0,
        output_tokens=session.get("output_tokens") or 0,
        cache_read_tokens=session.get("cache_read_tokens") or 0,
        cache_write_tokens=session.get("cache_write_tokens") or 0,
    )
    result = estimate_usage_cost(
        model,
        usage,
        provider=session.get("billing_provider"),
        base_url=session.get("billing_base_url"),
    )
    return float(result.amount_usd or 0.0), result.status


def _bar_chart(values: List[int], max_width: int = 15) -> List[str]:
    """创建水平条形图字符串"""
    peak = max(values) if values else 1
    if peak == 0:
        return ["" for _ in values]
    return [
        "█" * max(1, int(v / peak * max_width)) if v > 0 else ""
        for v in values
    ]


# ============================================================================
# InsightsEngine（增强版）
# ============================================================================

class InsightsEngine:
    """
    MimirAether 洞察引擎

    支持两种模式：
    1. SQL模式（推荐）：传入SessionDB实例，直接查询SQLite
    2. 内存模式（向后兼容）：无db参数，使用内存记录
    """

    # SQL模式：需要的sessions列（避免读取大字段）
    _SESSION_COLS = (
        "id, source, model, started_at, ended_at, "
        "message_count, tool_call_count, input_tokens, output_tokens, "
        "cache_read_tokens, cache_write_tokens, billing_provider, "
        "billing_base_url, billing_mode, estimated_cost_usd, "
        "actual_cost_usd, cost_status, cost_source"
    )

    _GET_SESSIONS_WITH_SOURCE = (
        f"SELECT {_SESSION_COLS} FROM sessions"
        " WHERE started_at >= ? AND source = ?"
        " ORDER BY started_at DESC"
    )
    _GET_SESSIONS_ALL = (
        f"SELECT {_SESSION_COLS} FROM sessions"
        " WHERE started_at >= ?"
        " ORDER BY started_at DESC"
    )

    def __init__(self, db=None):
        """
        Args:
            db: SessionDB实例或sqlite3连接（SQL模式），或None（内存模式）
        """
        self.db = db
        # 使用SessionDB的_conn来执行查询
        self._conn = db._conn if db else None
        self._db = db  # 保留SessionDB引用用于写入
        self._is_sql_mode = self._conn is not None

        # 内存模式兼容
        self.records: List[UsageRecord] = []
        self._session_cache: Dict[str, SessionInsights] = {}

    # =========================================================================
    # 公开API
    # =========================================================================

    def generate(self, days: int = 30, source: str = None) -> InsightsReport:
        """
        生成完整洞察报告

        Args:
            days: 回溯天数（默认30）
            source: 可选的平台过滤

        Returns:
            InsightsReport
        """
        if self._is_sql_mode:
            return self._generate_sql(days, source)
        else:
            return self._generate_memory(days, source)

    def record(
        self,
        metric: MetricType,
        value: float,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """记录指标（支持内存模式和SQL模式）"""
        record = UsageRecord(
            timestamp=datetime.now().isoformat(),
            metric=metric.value,
            value=value,
            metadata=metadata or {},
        )
        
        if self._is_sql_mode:
            # SQL模式：写入数据库
            self._write_to_db(record)
        else:
            # 内存模式
            self.records.append(record)
            if metadata.get("session_id"):
                self._update_session_insights(record)

    def record_message(
        self,
        session_id: str,
        role: str,
        token_count: int = 0,
        platform: str = "unknown"
    ) -> None:
        """记录消息（内存模式）"""
        if not self._is_sql_mode and token_count > 0:
            self.record(
                MetricType.TOKEN_INPUT if role == "user" else MetricType.TOKEN_OUTPUT,
                float(token_count),
                metadata={"session_id": session_id, "platform": platform},
            )

    def record_tool_call(
        self,
        session_id: str,
        tool_name: str,
        duration_ms: float,
        success: bool,
        platform: str = "unknown"
    ) -> None:
        """记录工具调用（内存 + SQL 模式）"""
        self.record(
            MetricType.TOOL_CALL,
            1,
            metadata={
                "session_id": session_id,
                "tool_name": tool_name,
                "duration_ms": duration_ms,
                "success": success,
                "platform": platform,
            },
        )

    def record_cost(
        self,
        session_id: str,
        input_tokens: int,
        output_tokens: int,
        model: str,
        platform: str = "unknown"
    ) -> None:
        """记录成本（内存模式）"""
        if not self._is_sql_mode:
            cost = self._estimate_cost_mem(input_tokens, output_tokens, model)
            self.record(
                MetricType.COST,
                cost,
                metadata={
                    "session_id": session_id,
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "model": model,
                    "platform": platform,
                },
            )

    def _estimate_cost_mem(
        self,
        input_tokens: int,
        output_tokens: int,
        model: str,
    ) -> float:
        """内存模式成本估算"""
        usage = CanonicalUsage(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )
        result = estimate_usage_cost(model, usage)
        return float(result.amount_usd or 0.0)

    def get_session_insights(self, session_id: str) -> Optional[SessionInsights]:
        """获取会话洞察（内存模式）"""
        return self._session_cache.get(session_id)

    def save(self, path: Optional[str] = None) -> None:
        """保存数据（内存模式）"""
        if self._is_sql_mode or not path:
            return
        try:
            data = {
                "records": [
                    {
                        "timestamp": r.timestamp,
                        "metric": r.metric,
                        "value": r.value,
                        "metadata": r.metadata,
                    }
                    for r in self.records
                ]
            }
            with open(path, "w") as f:
                json.dump(data, f)
            logger.info(f"Insights saved to {path}")
        except Exception as e:
            logger.error(f"Failed to save insights: {e}")

    def load(self, path: Optional[str] = None) -> None:
        """加载数据（内存模式）"""
        if self._is_sql_mode or not path:
            return
        try:
            with open(path, "r") as f:
                data = json.load(f)
            self.records = [
                UsageRecord(
                    timestamp=r["timestamp"],
                    metric=r["metric"],
                    value=r["value"],
                    metadata=r.get("metadata", {}),
                )
                for r in data.get("records", [])
            ]
            logger.info(f"Insights loaded from {path}")
        except Exception as e:
            logger.error(f"Failed to load insights: {e}")

    # =========================================================================
    # SQL模式实现
    # =========================================================================

    def _generate_sql(self, days: int, source: str) -> InsightsReport:
        """SQL模式：直接查询SessionDB"""
        cutoff = time.time() - (days * 86400)

        sessions = self._get_sessions(cutoff, source)
        tool_usage = self._get_tool_usage(cutoff, source)
        message_stats = self._get_message_stats(cutoff, source)

        if not sessions:
            return InsightsReport(
                days=days,
                source_filter=source,
                empty=True,
                generated_at=time.time(),
            )

        overview = self._compute_overview(sessions, message_stats)
        models = self._compute_model_breakdown(sessions)
        platforms = self._compute_platform_breakdown(sessions)
        tools = self._compute_tool_breakdown(tool_usage)
        activity = self._compute_activity_patterns(sessions)
        top_sessions = self._compute_top_sessions(sessions)

        return InsightsReport(
            days=days,
            source_filter=source,
            empty=False,
            generated_at=time.time(),
            total_sessions=overview["total_sessions"],
            total_messages=overview["total_messages"],
            total_tool_calls=overview["total_tool_calls"],
            total_input_tokens=overview["total_input_tokens"],
            total_output_tokens=overview["total_output_tokens"],
            total_cache_read_tokens=overview.get("total_cache_read_tokens", 0),
            total_cache_write_tokens=overview.get("total_cache_write_tokens", 0),
            total_tokens=overview["total_tokens"],
            estimated_cost=overview["estimated_cost"],
            actual_cost=overview.get("actual_cost", 0.0),
            total_hours=overview.get("total_hours", 0.0),
            avg_session_duration=overview.get("avg_session_duration", 0.0),
            avg_messages_per_session=overview.get("avg_messages_per_session", 0.0),
            avg_tokens_per_session=overview.get("avg_tokens_per_session", 0.0),
            user_messages=overview.get("user_messages", 0),
            assistant_messages=overview.get("assistant_messages", 0),
            tool_messages=overview.get("tool_messages", 0),
            date_range_start=overview.get("date_range_start"),
            date_range_end=overview.get("date_range_end"),
            models=models,
            models_with_pricing=overview.get("models_with_pricing", []),
            models_without_pricing=overview.get("models_without_pricing", []),
            unknown_cost_sessions=overview.get("unknown_cost_sessions", 0),
            included_cost_sessions=overview.get("included_cost_sessions", 0),
            platforms=platforms,
            tools=tools,
            activity=activity,
            top_sessions=top_sessions,
        )

    def _get_sessions(self, cutoff: float, source: str = None) -> List[Dict]:
        """获取会话列表"""
        if source:
            cursor = self._conn.execute(self._GET_SESSIONS_WITH_SOURCE, (cutoff, source))
        else:
            cursor = self._conn.execute(self._GET_SESSIONS_ALL, (cutoff,))
        return [dict(row) for row in cursor.fetchall()]

    def _get_tool_usage(self, cutoff: float, source: str = None) -> List[Dict]:
        """
        获取工具使用统计（双源：tool_name列 + tool_calls JSON）
        """
        tool_counts = Counter()

        # 源1：tool响应消息上的tool_name列
        if source:
            cursor = self._conn.execute(
                """SELECT m.tool_name, COUNT(*) as count
                   FROM messages m
                   JOIN sessions s ON s.id = m.session_id
                   WHERE s.started_at >= ? AND s.source = ?
                     AND m.role = 'tool' AND m.tool_name IS NOT NULL
                   GROUP BY m.tool_name
                   ORDER BY count DESC""",
                (cutoff, source),
            )
        else:
            cursor = self._conn.execute(
                """SELECT m.tool_name, COUNT(*) as count
                   FROM messages m
                   JOIN sessions s ON s.id = m.session_id
                   WHERE s.started_at >= ?
                     AND m.role = 'tool' AND m.tool_name IS NOT NULL
                   GROUP BY m.tool_name
                   ORDER BY count DESC""",
                (cutoff,),
            )
        for row in cursor.fetchall():
            tool_counts[row["tool_name"]] += row["count"]

        # 源2：从assistant消息的tool_calls JSON提取
        if source:
            cursor2 = self._conn.execute(
                """SELECT m.tool_calls
                   FROM messages m
                   JOIN sessions s ON s.id = m.session_id
                   WHERE s.started_at >= ? AND s.source = ?
                     AND m.role = 'assistant' AND m.tool_calls IS NOT NULL""",
                (cutoff, source),
            )
        else:
            cursor2 = self._conn.execute(
                """SELECT m.tool_calls
                   FROM messages m
                   JOIN sessions s ON s.id = m.session_id
                   WHERE s.started_at >= ?
                     AND m.role = 'assistant' AND m.tool_calls IS NOT NULL""",
                (cutoff,),
            )

        tool_calls_counts = Counter()
        for row in cursor2.fetchall():
            try:
                calls = row["tool_calls"]
                if isinstance(calls, str):
                    calls = json.loads(calls)
                if isinstance(calls, list):
                    for call in calls:
                        func = call.get("function", {}) if isinstance(call, dict) else {}
                        name = func.get("name")
                        if name:
                            tool_calls_counts[name] += 1
            except (json.JSONDecodeError, TypeError, AttributeError):
                continue

        # 合并：优先tool_name，补充tool_calls中未统计的工具
        if not tool_counts and tool_calls_counts:
            tool_counts = tool_calls_counts
        elif tool_counts and tool_calls_counts:
            all_tools = set(tool_counts) | set(tool_calls_counts)
            merged = Counter()
            for tool in all_tools:
                merged[tool] = max(
                    tool_counts.get(tool, 0),
                    tool_calls_counts.get(tool, 0),
                )
            tool_counts = merged

        return [
            {"tool_name": name, "count": count}
            for name, count in tool_counts.most_common()
        ]

    def _get_message_stats(self, cutoff: float, source: str = None) -> Dict:
        """获取消息统计"""
        if source:
            cursor = self._conn.execute(
                """SELECT
                     COUNT(*) as total_messages,
                     SUM(CASE WHEN m.role = 'user' THEN 1 ELSE 0 END) as user_messages,
                     SUM(CASE WHEN m.role = 'assistant' THEN 1 ELSE 0 END) as assistant_messages,
                     SUM(CASE WHEN m.role = 'tool' THEN 1 ELSE 0 END) as tool_messages
                   FROM messages m
                   JOIN sessions s ON s.id = m.session_id
                   WHERE s.started_at >= ? AND s.source = ?""",
                (cutoff, source),
            )
        else:
            cursor = self._conn.execute(
                """SELECT
                     COUNT(*) as total_messages,
                     SUM(CASE WHEN m.role = 'user' THEN 1 ELSE 0 END) as user_messages,
                     SUM(CASE WHEN m.role = 'assistant' THEN 1 ELSE 0 END) as assistant_messages,
                     SUM(CASE WHEN m.role = 'tool' THEN 1 ELSE 0 END) as tool_messages
                   FROM messages m
                   JOIN sessions s ON s.id = m.session_id
                   WHERE s.started_at >= ?""",
                (cutoff,),
            )
        row = cursor.fetchone()
        return dict(row) if row else {
            "total_messages": 0,
            "user_messages": 0,
            "assistant_messages": 0,
            "tool_messages": 0,
        }

    # =========================================================================
    # SQL模式统计计算
    # =========================================================================

    def _compute_overview(
        self,
        sessions: List[Dict],
        message_stats: Dict,
    ) -> Dict:
        """计算概览统计"""
        total_input = sum(s.get("input_tokens") or 0 for s in sessions)
        total_output = sum(s.get("output_tokens") or 0 for s in sessions)
        total_cache_read = sum(s.get("cache_read_tokens") or 0 for s in sessions)
        total_cache_write = sum(s.get("cache_write_tokens") or 0 for s in sessions)
        total_tokens = total_input + total_output + total_cache_read + total_cache_write
        total_tool_calls = sum(s.get("tool_call_count") or 0 for s in sessions)
        total_messages = sum(s.get("message_count") or 0 for s in sessions)

        # 成本估算
        total_cost = 0.0
        actual_cost = 0.0
        models_with_pricing = set()
        models_without_pricing = set()
        unknown_cost_sessions = 0
        included_cost_sessions = 0

        for s in sessions:
            model = s.get("model") or ""
            estimated, status = _estimate_cost_from_session(s)
            total_cost += estimated
            actual_cost += s.get("actual_cost_usd") or 0.0
            display = model.split("/")[-1] if "/" in model else (model or "unknown")
            if status == "included":
                included_cost_sessions += 1
            elif status == "unknown":
                unknown_cost_sessions += 1
            if _has_known_pricing(model, s.get("billing_provider"), s.get("billing_base_url")):
                models_with_pricing.add(display)
            else:
                models_without_pricing.add(display)

        # 会话时长统计
        durations = []
        for s in sessions:
            start = s.get("started_at")
            end = s.get("ended_at")
            if start and end and end > start:
                durations.append(end - start)

        total_hours = sum(durations) / 3600 if durations else 0
        avg_duration = sum(durations) / len(durations) if durations else 0

        # 日期范围
        started_timestamps = [s["started_at"] for s in sessions if s.get("started_at")]
        date_range_start = min(started_timestamps) if started_timestamps else None
        date_range_end = max(started_timestamps) if started_timestamps else None

        return {
            "total_sessions": len(sessions),
            "total_messages": total_messages,
            "total_tool_calls": total_tool_calls,
            "total_input_tokens": total_input,
            "total_output_tokens": total_output,
            "total_cache_read_tokens": total_cache_read,
            "total_cache_write_tokens": total_cache_write,
            "total_tokens": total_tokens,
            "estimated_cost": total_cost,
            "actual_cost": actual_cost,
            "total_hours": total_hours,
            "avg_session_duration": avg_duration,
            "avg_messages_per_session": total_messages / len(sessions) if sessions else 0,
            "avg_tokens_per_session": total_tokens / len(sessions) if sessions else 0,
            "user_messages": message_stats.get("user_messages") or 0,
            "assistant_messages": message_stats.get("assistant_messages") or 0,
            "tool_messages": message_stats.get("tool_messages") or 0,
            "date_range_start": date_range_start,
            "date_range_end": date_range_end,
            "models_with_pricing": sorted(models_with_pricing),
            "models_without_pricing": sorted(models_without_pricing),
            "unknown_cost_sessions": unknown_cost_sessions,
            "included_cost_sessions": included_cost_sessions,
        }

    def _compute_model_breakdown(self, sessions: List[Dict]) -> List[Dict]:
        """按模型分组统计"""
        model_data = defaultdict(
            lambda: {
                "sessions": 0,
                "input_tokens": 0,
                "output_tokens": 0,
                "cache_read_tokens": 0,
                "cache_write_tokens": 0,
                "total_tokens": 0,
                "tool_calls": 0,
                "cost": 0.0,
            }
        )

        for s in sessions:
            model = s.get("model") or "unknown"
            display_model = model.split("/")[-1] if "/" in model else model
            d = model_data[display_model]
            d["sessions"] += 1
            inp = s.get("input_tokens") or 0
            out = s.get("output_tokens") or 0
            cache_read = s.get("cache_read_tokens") or 0
            cache_write = s.get("cache_write_tokens") or 0
            d["input_tokens"] += inp
            d["output_tokens"] += out
            d["cache_read_tokens"] += cache_read
            d["cache_write_tokens"] += cache_write
            d["total_tokens"] += inp + out + cache_read + cache_write
            d["tool_calls"] += s.get("tool_call_count") or 0
            estimate, status = _estimate_cost_from_session(s)
            d["cost"] += estimate
            d["has_pricing"] = _has_known_pricing(
                model, s.get("billing_provider"), s.get("billing_base_url")
            )
            d["cost_status"] = status

        result = [
            {"model": model, **data}
            for model, data in model_data.items()
        ]
        result.sort(key=lambda x: (x["total_tokens"], x["sessions"]), reverse=True)
        return result

    def _compute_platform_breakdown(self, sessions: List[Dict]) -> List[Dict]:
        """按平台分组统计"""
        platform_data = defaultdict(
            lambda: {
                "sessions": 0,
                "messages": 0,
                "input_tokens": 0,
                "output_tokens": 0,
                "cache_read_tokens": 0,
                "cache_write_tokens": 0,
                "total_tokens": 0,
                "tool_calls": 0,
            }
        )

        for s in sessions:
            source = s.get("source") or "unknown"
            d = platform_data[source]
            d["sessions"] += 1
            d["messages"] += s.get("message_count") or 0
            inp = s.get("input_tokens") or 0
            out = s.get("output_tokens") or 0
            cache_read = s.get("cache_read_tokens") or 0
            cache_write = s.get("cache_write_tokens") or 0
            d["input_tokens"] += inp
            d["output_tokens"] += out
            d["cache_read_tokens"] += cache_read
            d["cache_write_tokens"] += cache_write
            d["total_tokens"] += inp + out + cache_read + cache_write
            d["tool_calls"] += s.get("tool_call_count") or 0

        result = [
            {"platform": platform, **data}
            for platform, data in platform_data.items()
        ]
        result.sort(key=lambda x: x["sessions"], reverse=True)
        return result

    def _compute_tool_breakdown(self, tool_usage: List[Dict]) -> List[Dict]:
        """工具使用排行"""
        total_calls = sum(t["count"] for t in tool_usage) if tool_usage else 0
        result = []
        for t in tool_usage:
            pct = (t["count"] / total_calls * 100) if total_calls else 0
            result.append({
                "tool": t["tool_name"],
                "count": t["count"],
                "percentage": pct,
            })
        return result

    def _compute_activity_patterns(self, sessions: List[Dict]) -> Dict:
        """活动模式分析"""
        day_counts = Counter()
        hour_counts = Counter()
        daily_counts = Counter()

        for s in sessions:
            ts = s.get("started_at")
            if not ts:
                continue
            dt = datetime.fromtimestamp(ts)
            day_counts[dt.weekday()] += 1
            hour_counts[dt.hour] += 1
            daily_counts[dt.strftime("%Y-%m-%d")] += 1

        day_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        day_breakdown = [
            {"day": day_names[i], "count": day_counts.get(i, 0)}
            for i in range(7)
        ]
        hour_breakdown = [
            {"hour": i, "count": hour_counts.get(i, 0)}
            for i in range(24)
        ]

        busiest_day = max(day_breakdown, key=lambda x: x["count"]) if day_breakdown else None
        busiest_hour = max(hour_breakdown, key=lambda x: x["count"]) if hour_breakdown else None
        active_days = len(daily_counts)

        # 连续天数计算
        max_streak = 0
        if daily_counts:
            all_dates = sorted(daily_counts.keys())
            current_streak = 1
            max_streak = 1
            for i in range(1, len(all_dates)):
                d1 = datetime.strptime(all_dates[i - 1], "%Y-%m-%d")
                d2 = datetime.strptime(all_dates[i], "%Y-%m-%d")
                if (d2 - d1).days == 1:
                    current_streak += 1
                    max_streak = max(max_streak, current_streak)
                else:
                    current_streak = 1

        return {
            "by_day": day_breakdown,
            "by_hour": hour_breakdown,
            "busiest_day": busiest_day,
            "busiest_hour": busiest_hour,
            "active_days": active_days,
            "max_streak": max_streak,
        }

    def _compute_top_sessions(self, sessions: List[Dict]) -> List[Dict]:
        """Top Sessions统计"""
        top = []

        # 最长会话
        sessions_with_duration = [
            s for s in sessions
            if s.get("started_at") and s.get("ended_at") and s["ended_at"] > s["started_at"]
        ]
        if sessions_with_duration:
            longest = max(
                sessions_with_duration,
                key=lambda s: s["ended_at"] - s["started_at"],
            )
            dur = longest["ended_at"] - longest["started_at"]
            top.append({
                "label": "Longest session",
                "session_id": longest["id"][:16],
                "value": format_duration_compact(dur),
                "date": datetime.fromtimestamp(longest["started_at"]).strftime("%b %d"),
            })

        # 最多消息
        most_msgs = max(sessions, key=lambda s: s.get("message_count") or 0)
        if (most_msgs.get("message_count") or 0) > 0:
            top.append({
                "label": "Most messages",
                "session_id": most_msgs["id"][:16],
                "value": f"{most_msgs['message_count']} msgs",
                "date": datetime.fromtimestamp(most_msgs["started_at"]).strftime("%b %d")
                    if most_msgs.get("started_at") else "?",
            })

        # 最多token
        most_tokens = max(
            sessions,
            key=lambda s: (s.get("input_tokens") or 0) + (s.get("output_tokens") or 0),
        )
        token_total = (most_tokens.get("input_tokens") or 0) + (most_tokens.get("output_tokens") or 0)
        if token_total > 0:
            top.append({
                "label": "Most tokens",
                "session_id": most_tokens["id"][:16],
                "value": f"{token_total:,} tokens",
                "date": datetime.fromtimestamp(most_tokens["started_at"]).strftime("%b %d")
                    if most_tokens.get("started_at") else "?",
            })

        # 最多工具调用
        most_tools = max(sessions, key=lambda s: s.get("tool_call_count") or 0)
        if (most_tools.get("tool_call_count") or 0) > 0:
            top.append({
                "label": "Most tool calls",
                "session_id": most_tools["id"][:16],
                "value": f"{most_tools['tool_call_count']} calls",
                "date": datetime.fromtimestamp(most_tools["started_at"]).strftime("%b %d")
                    if most_tools.get("started_at") else "?",
            })

        return top

    # =========================================================================
    # 内存模式实现
    # =========================================================================

    def _generate_memory(self, days: int, source: str) -> InsightsReport:
        """内存模式：基于in-memory records聚合"""
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        cutoff_str = cutoff.isoformat()

        recent = [r for r in self.records if r.timestamp >= cutoff_str]

        if not recent:
            return InsightsReport(
                days=days,
                source_filter=source,
                empty=True,
                generated_at=time.time(),
            )

        # 基础统计
        total_input = sum(
            r.value for r in recent
            if r.metric == MetricType.TOKEN_INPUT.value
        )
        total_output = sum(
            r.value for r in recent
            if r.metric == MetricType.TOKEN_OUTPUT.value
        )
        total_tokens = int(total_input + total_output)
        total_cost = sum(
            r.value for r in recent
            if r.metric == MetricType.COST.value
        )
        total_tool_calls = sum(
            1 for r in recent
            if r.metric == MetricType.TOOL_CALL.value
        )
        total_errors = sum(
            1 for r in recent
            if r.metric == MetricType.ERROR.value
        )
        sessions = set(
            r.metadata.get("session_id")
            for r in recent
            if r.metadata.get("session_id")
        )
        total_sessions = len(sessions)
        total_messages = total_tool_calls * 2  # 粗略估计

        # 工具排行
        tool_counts = Counter()
        for r in recent:
            if r.metric == MetricType.TOOL_CALL.value:
                tool_name = r.metadata.get("tool_name", "unknown")
                tool_counts[tool_name] += 1
        tool_breakdown = [
            {"tool": tool, "count": count, "percentage": 0.0}
            for tool, count in tool_counts.most_common()
        ]
        total_tool = sum(tool_counts.values())
        for t in tool_breakdown:
            t["percentage"] = (t["count"] / total_tool * 100) if total_tool > 0 else 0

        # 平台分布
        platform_counts = Counter()
        for r in recent:
            platform = r.metadata.get("platform", "unknown")
            if platform:
                platform_counts[platform] += 1
        platforms = [
            {"platform": p, "sessions": c, "messages": 0, "input_tokens": 0,
             "output_tokens": 0, "cache_read_tokens": 0, "cache_write_tokens": 0,
             "total_tokens": 0, "tool_calls": 0}
            for p, c in platform_counts.most_common()
        ]

        # 错误率
        total_ops = total_tool_calls + total_errors
        error_rate = total_errors / total_ops if total_ops > 0 else 0

        return InsightsReport(
            days=days,
            source_filter=source,
            empty=False,
            generated_at=time.time(),
            total_sessions=total_sessions,
            total_messages=total_messages,
            total_tool_calls=total_tool_calls,
            total_input_tokens=int(total_input),
            total_output_tokens=int(total_output),
            total_tokens=total_tokens,
            estimated_cost=total_cost,
            avg_tokens_per_session=total_tokens / total_sessions if total_sessions else 0,
            tools=tool_breakdown,
            platforms=platforms,
            activity={"error_rate": error_rate},
        )

    def _write_to_db(self, record: UsageRecord) -> None:
        """写入数据库（SQL模式）"""
        if not self._db or not record.metadata.get("session_id"):
            return
        
        session_id = record.metadata.get("session_id")
        model = record.metadata.get("model")
        platform = record.metadata.get("platform", "unknown")
        
        # 根据metric类型更新对应的token计数
        if record.metric == MetricType.TOKEN_INPUT.value:
            self._db.update_token_counts(
                session_id,
                input_tokens=int(record.value),
                model=model,
                billing_provider=platform,
            )
        elif record.metric == MetricType.TOKEN_OUTPUT.value:
            self._db.update_token_counts(
                session_id,
                output_tokens=int(record.value),
                model=model,
                billing_provider=platform,
            )
        elif record.metric == MetricType.TOOL_CALL.value:
            meta = record.metadata
            try:
                from agent.session_tracker import get_session_tracker

                get_session_tracker().record_tool_call(
                    session_id,
                    meta.get("tool_name", "unknown"),
                    success=bool(meta.get("success", True)),
                    duration_ms=float(meta.get("duration_ms", 0)),
                    error_msg=str(meta.get("error_message", "")),
                )
            except Exception:
                pass

    def _update_session_insights(self, record: UsageRecord) -> None:
        """更新会话洞察（内存模式）"""
        session_id = record.metadata.get("session_id")
        if not session_id:
            return

        if session_id not in self._session_cache:
            self._session_cache[session_id] = SessionInsights(
                session_id=session_id,
                start_time=record.timestamp,
                platform=record.metadata.get("platform", "unknown"),
            )

        insights = self._session_cache[session_id]
        if record.metric in (MetricType.TOKEN_INPUT.value, MetricType.TOKEN_OUTPUT.value):
            insights.total_tokens += int(record.value)
        elif record.metric == MetricType.COST.value:
            insights.total_cost += record.value
        elif record.metric == MetricType.TOOL_CALL.value:
            insights.tool_calls += 1
        elif record.metric == MetricType.ERROR.value:
            insights.errors += 1

    # =========================================================================
    # 格式化输出
    # =========================================================================

    def format_terminal(self, report: InsightsReport) -> str:
        """终端格式化输出（ASCII art）"""
        if report.empty:
            days = report.days
            src = f" (source: {report.source_filter})" if report.source_filter else ""
            return f"  No sessions found in the last {days} days{src}."

        lines = []
        days = report.days
        src_filter = report.source_filter

        # Header
        lines.append("")
        lines.append("  ╔══════════════════════════════════════════════════════════╗")
        lines.append("  ║              📊 MimirAether Insights                     ║")
        period_label = f"Last {days} days"
        if src_filter:
            period_label += f" ({src_filter})"
        padding = 58 - len(period_label) - 2
        left_pad = padding // 2
        right_pad = padding - left_pad
        lines.append(f"  ║{' ' * left_pad} {period_label} {' ' * right_pad}║")
        lines.append("  ╚══════════════════════════════════════════════════════════╝")
        lines.append("")

        # Date range
        if report.date_range_start and report.date_range_end:
            start_str = datetime.fromtimestamp(report.date_range_start).strftime("%b %d, %Y")
            end_str = datetime.fromtimestamp(report.date_range_end).strftime("%b %d, %Y")
            lines.append(f"  Period: {start_str} — {end_str}")
            lines.append("")

        # Overview
        lines.append("  📋 Overview")
        lines.append("  " + "─" * 56)
        lines.append(
            f"  Sessions:          {report.total_sessions:<12}  "
            f"Messages:        {report.total_messages:,}"
        )
        lines.append(
            f"  Tool calls:        {report.total_tool_calls:<12,}  "
            f"User messages:   {report.user_messages:,}"
        )
        lines.append(
            f"  Input tokens:      {report.total_input_tokens:<12,}  "
            f"Output tokens:   {report.total_output_tokens:,}"
        )
        cache_total = report.total_cache_read_tokens + report.total_cache_write_tokens
        if cache_total > 0:
            lines.append(
                f"  Cache read:        {report.total_cache_read_tokens:<12,}  "
                f"Cache write:     {report.total_cache_write_tokens:,}"
            )
        cost_str = f"${report.estimated_cost:.2f}"
        if report.models_without_pricing:
            cost_str += " *"
        lines.append(
            f"  Total tokens:      {report.total_tokens:<12,}  "
            f"Est. cost:       {cost_str}"
        )
        if report.total_hours > 0:
            lines.append(
                f"  Active time:       ~{format_duration_compact(report.total_hours * 3600):<11}  "
                f"Avg session:     ~{format_duration_compact(report.avg_session_duration)}"
            )
        lines.append(f"  Avg msgs/session:  {report.avg_messages_per_session:.1f}")
        lines.append("")

        # Model breakdown
        if report.models:
            lines.append("  🤖 Models Used")
            lines.append("  " + "─" * 56)
            lines.append(f"  {'Model':<30} {'Sessions':>8} {'Tokens':>12} {'Cost':>8}")
            for m in report.models:
                model_name = m["model"][:28]
                if m.get("has_pricing"):
                    cost_cell = f"${m['cost']:>6.2f}"
                else:
                    cost_cell = "     N/A"
                lines.append(
                    f"  {model_name:<30} {m['sessions']:>8} "
                    f"{m['total_tokens']:>12,} {cost_cell}"
                )
            if report.models_without_pricing:
                lines.append("  * Cost N/A for custom/self-hosted models")
            lines.append("")

        # Platform breakdown
        if len(report.platforms) > 1 or (
            report.platforms and report.platforms[0]["platform"] != "cli"
        ):
            lines.append("  📱 Platforms")
            lines.append("  " + "─" * 56)
            lines.append(
                f"  {'Platform':<14} {'Sessions':>8} {'Messages':>10} {'Tokens':>14}"
            )
            for p in report.platforms:
                lines.append(
                    f"  {p['platform']:<14} {p['sessions']:>8} "
                    f"{p['messages']:>10,} {p['total_tokens']:>14,}"
                )
            lines.append("")

        # Tool usage
        if report.tools:
            lines.append("  🔧 Top Tools")
            lines.append("  " + "─" * 56)
            lines.append(f"  {'Tool':<28} {'Calls':>8} {'%':>8}")
            for t in report.tools[:15]:
                lines.append(
                    f"  {t['tool']:<28} {t['count']:>8,} {t['percentage']:>7.1f}%"
                )
            if len(report.tools) > 15:
                lines.append(f"  ... and {len(report.tools) - 15} more tools")
            lines.append("")

        # Activity patterns
        act = report.activity
        if act.get("by_day"):
            lines.append("  📅 Activity Patterns")
            lines.append("  " + "─" * 56)

            day_values = [d["count"] for d in act["by_day"]]
            bars = _bar_chart(day_values, max_width=15)
            for i, d in enumerate(act["by_day"]):
                lines.append(f"  {d['day']}  {bars[i]:<15} {d['count']}")
            lines.append("")

            # Peak hours
            busy_hours = sorted(act["by_hour"], key=lambda x: x["count"], reverse=True)
            busy_hours = [h for h in busy_hours if h["count"] > 0][:5]
            if busy_hours:
                hour_strs = []
                for h in busy_hours:
                    hr = h["hour"]
                    ampm = "AM" if hr < 12 else "PM"
                    display_hr = hr % 12 or 12
                    hour_strs.append(f"{display_hr}{ampm} ({h['count']})")
                lines.append(f"  Peak hours: {', '.join(hour_strs)}")

            if act.get("active_days"):
                lines.append(f"  Active days: {act['active_days']}")
            if act.get("max_streak", 0) > 1:
                lines.append(f"  Best streak: {act['max_streak']} consecutive days")
            lines.append("")

        # Notable sessions
        if report.top_sessions:
            lines.append("  🏆 Notable Sessions")
            lines.append("  " + "─" * 56)
            for ts in report.top_sessions:
                lines.append(
                    f"  {ts['label']:<20} {ts['value']:<18} "
                    f"({ts['date']}, {ts['session_id']})"
                )
            lines.append("")

        return "\n".join(lines)

    def format_gateway(self, report: InsightsReport) -> str:
        """网关格式化输出（短格式消息）"""
        if report.empty:
            days = report.days
            return f"No sessions found in the last {days} days."

        lines = []
        days = report.days

        lines.append(f"📊 **MimirAether Insights** — Last {days} days\n")

        # Overview
        lines.append(
            f"**Sessions:** {report.total_sessions} | "
            f"**Messages:** {report.total_messages:,} | "
            f"**Tool calls:** {report.total_tool_calls:,}"
        )
        cache_total = report.total_cache_read_tokens + report.total_cache_write_tokens
        if cache_total > 0:
            lines.append(
                f"**Tokens:** {report.total_tokens:,} "
                f"(in: {report.total_input_tokens:,} / "
                f"out: {report.total_output_tokens:,} / "
                f"cache: {cache_total:,})"
            )
        else:
            lines.append(
                f"**Tokens:** {report.total_tokens:,} "
                f"(in: {report.total_input_tokens:,} / "
                f"out: {report.total_output_tokens:,})"
            )
        cost_note = ""
        if report.models_without_pricing:
            cost_note = " _(excludes custom/self-hosted models)_"
        lines.append(f"**Est. cost:** ${report.estimated_cost:.2f}{cost_note}")
        if report.total_hours > 0:
            lines.append(
                f"**Active time:** ~{format_duration_compact(report.total_hours * 3600)} | "
                f"**Avg session:** ~{format_duration_compact(report.avg_session_duration)}"
            )
        lines.append("")

        # Models (top 5)
        if report.models:
            lines.append("**🤖 Models:**")
            for m in report.models[:5]:
                cost_str = f"${m['cost']:.2f}" if m.get("has_pricing") else "N/A"
                lines.append(
                    f"  {m['model'][:25]} — {m['sessions']} sessions, "
                    f"{m['total_tokens']:,} tokens, {cost_str}"
                )
            lines.append("")

        # Platforms (if multi-platform)
        if len(report.platforms) > 1:
            lines.append("**📱 Platforms:**")
            for p in report.platforms:
                lines.append(
                    f"  {p['platform']} — {p['sessions']} sessions, "
                    f"{p['messages']:,} msgs"
                )
            lines.append("")

        # Tools (top 8)
        if report.tools:
            lines.append("**🔧 Top Tools:**")
            for t in report.tools[:8]:
                lines.append(
                    f"  {t['tool']} — {t['count']:,} calls ({t['percentage']:.1f}%)"
                )
            lines.append("")

        # Activity summary
        act = report.activity
        if act.get("busiest_day") and act.get("busiest_hour"):
            hr = act["busiest_hour"]["hour"]
            ampm = "AM" if hr < 12 else "PM"
            display_hr = hr % 12 or 12
            lines.append(
                f"**📅 Busiest:** {act['busiest_day']['day']}s "
                f"({act['busiest_day']['count']} sessions), "
                f"{display_hr}{ampm} ({act['busiest_hour']['count']} sessions)"
            )
            if act.get("active_days"):
                lines.append(f"**Active days:** {act['active_days']}")
            if act.get("max_streak", 0) > 1:
                lines.append(f"**Best streak:** {act['max_streak']} consecutive days")

        return "\n".join(lines)


# ============================================================================
# 便捷函数（向后兼容）
# ============================================================================
# Hermès兼容函数（补充）
# ============================================================================

def _estimate_cost(
    session_or_model: Dict[str, Any] | str,
    input_tokens: int = 0,
    output_tokens: int = 0,
    *,
    cache_read_tokens: int = 0,
    cache_write_tokens: int = 0,
    provider: str = None,
    base_url: str = None,
) -> tuple[float, str]:
    """
    估算会话或模型的USD成本（Hermès兼容签名）

    支持两种调用方式：
    1. _estimate_cost(session_dict) - 从会话字典估算
    2. _estimate_cost(model_name, input_tokens, output_tokens, ...) - 直接估算

    Args:
        session_or_model: 会话字典或模型名字符串
        input_tokens: 输入token数（model参数时使用）
        output_tokens: 输出token数（model参数时使用）
        cache_read_tokens: 缓存读取token数
        cache_write_tokens: 缓存写入token数
        provider: 提供商名称
        base_url: API基础URL

    Returns:
        (成本USD, 状态字符串)
    """
    if isinstance(session_or_model, dict):
        session = session_or_model
        model = session.get("model") or ""
        usage = CanonicalUsage(
            input_tokens=session.get("input_tokens") or 0,
            output_tokens=session.get("output_tokens") or 0,
            cache_read_tokens=session.get("cache_read_tokens") or 0,
            cache_write_tokens=session.get("cache_write_tokens") or 0,
        )
        provider = session.get("billing_provider") or provider
        base_url = session.get("billing_base_url") or base_url
    else:
        model = session_or_model or ""
        usage = CanonicalUsage(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cache_read_tokens=cache_read_tokens,
            cache_write_tokens=cache_write_tokens,
        )

    result = estimate_usage_cost(
        model,
        usage,
        provider=provider,
        base_url=base_url,
    )
    return float(result.amount_usd or 0.0), result.status


def _format_duration(seconds: float) -> str:
    """格式化秒数为可读时长字符串（Hermès兼容）"""
    return format_duration_compact(seconds)


# ============================================================================

_default_engine: Optional[InsightsEngine] = None


def get_insights() -> InsightsEngine:
    """获取全局洞察引擎实例（内存模式）"""
    global _default_engine
    if _default_engine is None:
        _default_engine = InsightsEngine()
    return _default_engine


# ============================================================================
# 导出
# ============================================================================

__all__ = [
    "InsightsEngine",
    "InsightsReport",
    "SessionInsights",
    "MetricType",
    "UsageRecord",
    "get_insights",
    "_estimate_cost",
    "_format_duration",
]
