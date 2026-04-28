"""
# MimirAether Type System
# 统一数据类型定义 - 解决重复定义问题

从 core_loop.py 和 agent_loop.py 提取的所有共享数据类型。
所有模块应从此处导入，而非自行定义。
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Union
from enum import Enum


class MessageRole(Enum):
    """消息角色"""
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


@dataclass
class Message:
    """对话消息"""
    role: MessageRole
    content: str
    name: Optional[str] = None
    tool_calls: Optional[List[Dict]] = None
    tool_call_id: Optional[str] = None
    reasoning_content: Optional[str] = None  # DeepSeek V4 Pro reasoning


@dataclass
class ToolCall:
    """工具调用"""
    id: str
    name: str
    arguments: Union[str, Dict[str, Any]]


@dataclass
class ToolResult:
    """工具执行结果"""
    tool_call_id: str
    content: str
    is_error: bool = False


@dataclass
class ToolError:
    """
    工具执行错误记录

    学习自Hermes ToolError:收集工具执行错误,不中断流程,
    但记录完整上下文用于调试和分析。
    """
    turn: int                    # 哪个轮次出错
    tool_name: str               # 工具名
    arguments: str               # 参数(截断到200字符)
    error: str                   # 错误类型和消息
    tool_result: str             # 返回给模型的原始结果(截断)


@dataclass
class ExecutionMetadata:
    """
    执行元数据

    学习自Hermes AgentResult:返回完整执行元数据,
    便于分析、调试和续传。
    """
    turns_used: int = 0                    # LLM调用次数
    finished_naturally: bool = False        # 是否自然结束(非max_turns)
    reasoning_per_turn: List[str] = field(default_factory=list)  # 每轮推理内容
    tool_errors: List[ToolError] = field(default_factory=list)  # 工具错误列表
    total_api_time_ms: float = 0.0         # 总API调用时间
    total_tool_time_ms: float = 0.0         # 总工具执行时间


@dataclass
class Plan:
    """任务分解计划"""
    task: str
    subtasks: List[Dict[str, Any]] = field(default_factory=list)
    complexity: int = 0
    estimated_time: int = 0


@dataclass
class ExecutionResult:
    """执行结果"""
    success: bool
    output: Any
    error: Optional[str] = None
    tool_calls_made: int = 0
    duration: float = 0.0


# ──────────────────────────────────────────────
# 工具调用格式工具函数
# 兼容OpenAI格式: {"type": "function", "function": {"name": "xxx", "arguments": "..."}}
# 和旧格式: {"name": "xxx", "arguments": {...}}
# ──────────────────────────────────────────────

def _get_tool_name(tc: dict) -> str:
    """从工具调用dict中提取工具名称，兼容OpenAI嵌套格式和旧格式。"""
    if not isinstance(tc, dict):
        return ""
    func = tc.get("function")
    if isinstance(func, dict):
        name = func.get("name")
        if name:
            return name
    return tc.get("name", "")


def _get_tool_arguments(tc: dict) -> str:
    """从工具调用dict中提取arguments，兼容OpenAI嵌套格式和旧格式。"""
    if not isinstance(tc, dict):
        return ""
    func = tc.get("function")
    if isinstance(func, dict):
        if "arguments" in func:
            return func["arguments"]
    if "arguments" in tc:
        return tc["arguments"]
    return ""


def _get_tool_id(tc: dict) -> str:
    """从工具调用dict中提取id。"""
    if isinstance(tc, dict):
        return tc.get("id", "")
    return ""


# ──────────────────────────────────────────────
# 向后兼容: 从 agent_loop.py 提取的重复类型
# ──────────────────────────────────────────────

@dataclass
class AgentLoopToolError:
    """Tool execution error record (Hermes pattern) - from agent_loop.py."""
    turn: int
    tool_name: str
    arguments: str  # truncated to 200 chars
    error: str
    tool_result: str


@dataclass
class AgentLoopResult:
    """Agent loop execution result (Hermes pattern) - from agent_loop.py."""
    messages: List[Dict[str, Any]]
    turns_used: int = 0
    finished_naturally: bool = False
    reasoning_per_turn: List[Optional[str]] = field(default_factory=list)
    tool_errors: List[AgentLoopToolError] = field(default_factory=list)
    interrupted: bool = False


# 向后兼容别名
AgentResult = AgentLoopResult


# 导出所有类型
__all__ = [
    # Enums
    "MessageRole",
    # Core types
    "Message",
    "ToolCall",
    "ToolResult",
    "ToolError",
    "ExecutionMetadata",
    "Plan",
    "ExecutionResult",
    # From agent_loop.py
    "AgentLoopToolError",
    "AgentLoopResult",
    "AgentResult",  # alias for backward compat
    # Helper functions
    "_get_tool_name",
    "_get_tool_arguments",
    "_get_tool_id",
]
