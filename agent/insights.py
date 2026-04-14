"""
Insights Engine - 洞察引擎

追踪和分析Agent使用情况，包括：
- Token消耗统计
- 成本估算
- 工具使用模式
- 会话活动趋势
- 模型/平台分布

学习自Hermes Insights Engine。
"""

import json
import logging
import time
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


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
    """洞察报告"""
    period_start: str
    period_end: str
    total_sessions: int
    total_messages: int
    total_tokens: int
    total_cost: float
    avg_turns_per_session: float
    top_tools: List[tuple]
    error_rate: float
    platform_breakdown: Dict[str, int]
    hourly_activity: Dict[int, int]


class InsightsEngine:
    """
    洞察引擎
    
    收集、聚合、分析Agent使用数据。
    """
    
    # 默认定价（每1M tokens）
    DEFAULT_PRICING = {
        "claude-3-5-sonnet": {"input": 3.0, "output": 15.0},
        "claude-3-opus": {"input": 15.0, "output": 75.0},
        "gpt-4o": {"input": 5.0, "output": 15.0},
        "gpt-4-turbo": {"input": 10.0, "output": 30.0},
        "default": {"input": 5.0, "output": 15.0},
    }
    
    def __init__(self, storage_path: Optional[str] = None):
        """
        Args:
            storage_path: 数据存储路径
        """
        self.storage_path = storage_path
        self.records: List[UsageRecord] = []
        self._session_cache: Dict[str, SessionInsights] = {}
    
    def record(
        self,
        metric: MetricType,
        value: float,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """记录一个指标"""
        record = UsageRecord(
            timestamp=datetime.now().isoformat(),
            metric=metric.value,
            value=value,
            metadata=metadata or {}
        )
        self.records.append(record)
        
        # 实时更新会话洞察
        if metadata.get("session_id"):
            self._update_session_insights(record)
    
    def _update_session_insights(self, record: UsageRecord) -> None:
        """更新会话洞察"""
        session_id = record.metadata.get("session_id")
        if not session_id:
            return
        
        if session_id not in self._session_cache:
            self._session_cache[session_id] = SessionInsights(
                session_id=session_id,
                start_time=record.timestamp,
                platform=record.metadata.get("platform", "unknown")
            )
        
        insights = self._session_cache[session_id]
        
        # 更新指标
        if record.metric == MetricType.TOKEN_INPUT.value:
            insights.total_tokens += record.value
        elif record.metric == MetricType.TOKEN_OUTPUT.value:
            insights.total_tokens += record.value
        elif record.metric == MetricType.COST.value:
            insights.total_cost += record.value
        elif record.metric == MetricType.TOOL_CALL.value:
            insights.tool_calls += 1
        elif record.metric == MetricType.ERROR.value:
            insights.errors += 1
    
    def record_message(
        self,
        session_id: str,
        role: str,
        token_count: int = 0,
        platform: str = "unknown"
    ) -> None:
        """记录消息
        
        Args:
            session_id: 会话ID
            role: 角色(user/assistant)
            token_count: token数量（必须传入实际值）
            platform: 平台
        """
        if token_count <= 0:
            logger.warning(f"record_message called with token_count={token_count}, session={session_id}")
        self.record(
            MetricType.TOKEN_INPUT if role == "user" else MetricType.TOKEN_OUTPUT,
            float(token_count),
            metadata={"session_id": session_id, "platform": platform}
        )
    
    def record_tool_call(
        self,
        session_id: str,
        tool_name: str,
        duration_ms: float,
        success: bool,
        platform: str = "unknown"
    ) -> None:
        """记录工具调用"""
        self.record(
            MetricType.TOOL_CALL,
            1,
            metadata={
                "session_id": session_id,
                "tool_name": tool_name,
                "duration_ms": duration_ms,
                "success": success,
                "platform": platform
            }
        )
    
    def record_cost(
        self,
        session_id: str,
        input_tokens: int,
        output_tokens: int,
        model: str,
        platform: str = "unknown"
    ) -> None:
        """记录成本"""
        cost = self.estimate_cost(input_tokens, output_tokens, model)
        self.record(
            MetricType.COST,
            cost,
            metadata={
                "session_id": session_id,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "model": model,
                "platform": platform
            }
        )
    
    def estimate_cost(
        self,
        input_tokens: int,
        output_tokens: int,
        model: str
    ) -> float:
        """估算成本"""
        # 获取模型定价
        pricing = self.DEFAULT_PRICING.get(model, self.DEFAULT_PRICING["default"])
        
        input_cost = (input_tokens / 1_000_000) * pricing["input"]
        output_cost = (output_tokens / 1_000_000) * pricing["output"]
        
        return input_cost + output_cost
    
    def get_session_insights(self, session_id: str) -> Optional[SessionInsights]:
        """获取会话洞察"""
        return self._session_cache.get(session_id)
    
    def generate_report(self, days: int = 7) -> InsightsReport:
        """
        生成使用报告
        
        Args:
            days: 报告周期（天数）
        """
        # 过滤指定周期内的记录
        cutoff = datetime.now() - timedelta(days=days)
        cutoff_str = cutoff.isoformat()
        
        recent_records = [r for r in self.records if r.timestamp >= cutoff_str]
        
        # 聚合统计
        total_messages = len([r for r in recent_records if r.metric in 
                           [MetricType.TOKEN_INPUT.value, MetricType.TOKEN_OUTPUT.value]])
        total_tokens = sum(r.value for r in recent_records 
                         if r.metric in [MetricType.TOKEN_INPUT.value, MetricType.TOKEN_OUTPUT.value])
        total_cost = sum(r.value for r in recent_records if r.metric == MetricType.COST.value)
        total_tool_calls = sum(1 for r in recent_records if r.metric == MetricType.TOOL_CALL.value)
        total_errors = sum(1 for r in recent_records if r.metric == MetricType.ERROR.value)
        
        # 会话统计
        sessions = set(r.metadata.get("session_id") for r in recent_records if r.metadata.get("session_id"))
        total_sessions = len(sessions)
        avg_turns = total_tool_calls / total_sessions if total_sessions > 0 else 0
        
        # 工具使用排行
        tool_counts = Counter()
        for r in recent_records:
            if r.metric == MetricType.TOOL_CALL.value:
                tool_name = r.metadata.get("tool_name", "unknown")
                tool_counts[tool_name] += 1
        top_tools = tool_counts.most_common(10)
        
        # 错误率
        total_ops = total_tool_calls + total_errors
        error_rate = total_errors / total_ops if total_ops > 0 else 0
        
        # 平台分布
        platform_counts = Counter()
        for r in recent_records:
            platform = r.metadata.get("platform", "unknown")
            if platform:
                platform_counts[platform] += 1
        
        # 小时活动分布
        hourly = defaultdict(int)
        for r in recent_records:
            try:
                hour = datetime.fromisoformat(r.timestamp).hour
                hourly[hour] += 1
            except:
                pass
        
        return InsightsReport(
            period_start=cutoff_str,
            period_end=datetime.now().isoformat(),
            total_sessions=total_sessions,
            total_messages=total_messages,
            total_tokens=total_tokens,
            total_cost=total_cost,
            avg_turns_per_session=avg_turns,
            top_tools=top_tools,
            error_rate=error_rate,
            platform_breakdown=dict(platform_counts),
            hourly_activity=dict(hourly),
        )
    
    def format_terminal(self, report: InsightsReport) -> str:
        """格式化报告为终端输出"""
        lines = [
            "=" * 60,
            "📊 MimirAether Insights Report",
            "=" * 60,
            f"Period: {report.period_start[:10]} to {report.period_end[:10]}",
            "-" * 60,
            f"Sessions:     {report.total_sessions}",
            f"Messages:     {report.total_messages}",
            f"Total Tokens: {report.total_tokens:,}",
            f"Total Cost:   ${report.total_cost:.4f}",
            f"Avg Turns:    {report.avg_turns_per_session:.1f}/session",
            f"Error Rate:   {report.error_rate*100:.1f}%",
            "-" * 60,
            "Top Tools:",
        ]
        
        for tool, count in report.top_tools[:5]:
            lines.append(f"  {tool}: {count}")
        
        lines.extend([
            "-" * 60,
            "Platform Distribution:",
        ])
        
        for platform, count in report.platform_breakdown.items():
            lines.append(f"  {platform}: {count}")
        
        lines.append("=" * 60)
        
        return "\n".join(lines)
    
    def save(self, path: Optional[str] = None) -> None:
        """保存数据"""
        path = path or self.storage_path
        if not path:
            return
        
        data = {
            "records": [
                {
                    "timestamp": r.timestamp,
                    "metric": r.metric,
                    "value": r.value,
                    "metadata": r.metadata
                }
                for r in self.records
            ]
        }
        
        try:
            with open(path, "w") as f:
                json.dump(data, f)
            logger.info(f"Insights saved to {path}")
        except Exception as e:
            logger.error(f"Failed to save insights: {e}")
    
    def load(self, path: Optional[str] = None) -> None:
        """加载数据"""
        path = path or self.storage_path
        if not path:
            return
        
        try:
            with open(path, "r") as f:
                data = json.load(f)
            
            self.records = [
                UsageRecord(
                    timestamp=r["timestamp"],
                    metric=r["metric"],
                    value=r["value"],
                    metadata=r.get("metadata", {})
                )
                for r in data.get("records", [])
            ]
            logger.info(f"Insights loaded from {path}")
        except Exception as e:
            logger.error(f"Failed to load insights: {e}")


# 便捷函数
_default_engine: Optional[InsightsEngine] = None


def get_insights() -> InsightsEngine:
    """获取全局洞察引擎实例"""
    global _default_engine
    if _default_engine is None:
        _default_engine = InsightsEngine()
    return _default_engine


# 导出
__all__ = [
    "InsightsEngine",
    "InsightsReport",
    "SessionInsights",
    "MetricType",
    "UsageRecord",
    "get_insights",
]
