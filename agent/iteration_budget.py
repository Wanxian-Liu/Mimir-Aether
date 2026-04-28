"""
Enhanced IterationBudget Module for MimirAether

学习自Hermes IterationBudget，增强功能:
- 精细化迭代控制
- 预算预警和动态调整
- 工具类别预算分配
- 迭代历史追踪

Author: MimirAether (self-evolved)
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Set

logger = logging.getLogger(__name__)


class BudgetWarning(Enum):
    """预算警告级别"""
    SAFE = "safe"           # 安全
    WARNING = "warning"     # 警告 (< 30%)
    CRITICAL = "critical"   # 危险 (< 10%)
    EXHAUSTED = "exhausted" # 耗尽


@dataclass
class BudgetStats:
    """预算统计"""
    total_iterations: int = 0
    successful_iterations: int = 0
    forced_terminations: int = 0
    compression_triggered: int = 0
    avg_turns_per_task: float = 0.0
    peak_usage_time: float = 0.0
    
    # 工具使用统计
    tool_usage: Dict[str, int] = field(default_factory=dict)
    expensive_tools: Set[str] = field(default_factory=set)


@dataclass
class IterationRecord:
    """单次迭代记录"""
    turn: int
    action: str  # "api_call", "tool", "compression", etc.
    tool_name: Optional[str] = None
    success: bool = True
    duration_ms: float = 0.0
    tokens_used: int = 0
    timestamp: float = field(default_factory=time.time)


class EnhancedIterationBudget:
    """
    增强版迭代预算控制器
    
    学习自Hermes:
    - 父Agent默认90次迭代
    - 子Agent默认50次迭代
    - execute_code等工具调用不消耗预算
    
    新增功能:
    - 预算预警系统
    - 工具类别预算分配
    - 迭代历史追踪
    - 动态预算调整
    """
    
    # 不消耗预算的工具
    FREE_TOOLS: Set[str] = {
        "execute_code",
        "bash", 
        "run_command",
        "subprocess",
    }
    
    # 高消耗工具（每个调用消耗2次迭代）
    EXPENSIVE_TOOLS: Set[str] = {
        "browser",
        "web_search",
        "delegate",
        "spawn_agent",
    }
    
    def __init__(
        self,
        max_total: int = 90,
        warning_threshold: float = 0.3,
        critical_threshold: float = 0.1,
        track_history: bool = True,
        max_history: int = 1000,
    ):
        self.max_total = max_total
        self._used = 0
        self._lock = asyncio.Lock()
        
        # 阈值
        self.warning_threshold = warning_threshold
        self.critical_threshold = critical_threshold
        
        # 历史追踪
        self.track_history = track_history
        self.max_history = max_history
        self._history: List[IterationRecord] = []
        
        # 统计
        self.stats = BudgetStats()
        
        # 任务上下文
        self._task_start_time: Optional[float] = None
        self._current_task_turns: int = 0
        
        # 工具预算
        self._tool_budgets: Dict[str, int] = {}
        
        logger.debug(f"EnhancedIterationBudget initialized: max={max_total}")
    
    async def consume(self, tool_name: Optional[str] = None) -> bool:
        """
        尝试消耗一次迭代
        
        Args:
            tool_name: 工具名称（可选，用于追踪）
            
        Returns:
            是否成功消耗（还有预算）
        """
        async with self._lock:
            if self._used >= self.max_total:
                self.stats.forced_terminations += 1
                return False
            
            # 检查工具预算
            if tool_name and tool_name in self._tool_budgets:
                if self._tool_budgets[tool_name] <= 0:
                    logger.warning(f"Tool budget exhausted: {tool_name}")
                    return False
            
            self._used += 1
            self.stats.total_iterations += 1
            self._current_task_turns += 1
            
            # 记录历史
            if self.track_history:
                self._record_iteration(action="iteration" if not tool_name else "tool", 
                                      tool_name=tool_name)
            
            # 更新工具统计
            if tool_name:
                self.stats.tool_usage[tool_name] = self.stats.tool_usage.get(tool_name, 0) + 1
                
                # 标记高消耗工具
                if tool_name in self.EXPENSIVE_TOOLS:
                    self.stats.expensive_tools.add(tool_name)
            
            # 更新峰值
            remaining = self.max_total - self._used
            if remaining < self.max_total * self.critical_threshold:
                self.stats.peak_usage_time = time.time()
            
            return True
    
    async def refund(self) -> None:
        """退还一次迭代（如execute_code不消耗预算）"""
        async with self._lock:
            if self._used > 0:
                self._used -= 1
    
    async def get_remaining(self) -> int:
        """获取剩余迭代次数（异步安全）"""
        async with self._lock:
            return self.max_total - self._used
    
    def get_warning_level(self) -> BudgetWarning:
        """获取当前预算警告级别"""
        remaining = self.max_total - self._used
        ratio = remaining / self.max_total
        
        if ratio <= 0:
            return BudgetWarning.EXHAUSTED
        elif ratio <= self.critical_threshold:
            return BudgetWarning.CRITICAL
        elif ratio <= self.warning_threshold:
            return BudgetWarning.WARNING
        else:
            return BudgetWarning.SAFE
    
    def is_safe_to_continue(self) -> bool:
        """是否可以安全继续"""
        return self._used < self.max_total
    
    def should_warn(self) -> bool:
        """是否应该发出警告"""
        level = self.get_warning_level()
        return level in (BudgetWarning.WARNING, BudgetWarning.CRITICAL)
    
    def _record_iteration(self, action: str, tool_name: Optional[str] = None) -> None:
        """记录迭代历史"""
        record = IterationRecord(
            turn=len(self._history) + 1,
            action=action,
            tool_name=tool_name,
        )
        self._history.append(record)
        
        # 限制历史长度
        if len(self._history) > self.max_history:
            self._history = self._history[-self.max_history:]
    
    def set_tool_budget(self, tool_name: str, budget: int) -> None:
        """设置工具预算"""
        self._tool_budgets[tool_name] = budget
    
    def consume_tool_budget(self, tool_name: str) -> bool:
        """消耗工具预算"""
        if tool_name not in self._tool_budgets:
            return True  # 无预算限制
        
        if self._tool_budgets[tool_name] > 0:
            self._tool_budgets[tool_name] -= 1
            return True
        return False
    
    def start_task(self) -> None:
        """开始新任务"""
        self._task_start_time = time.time()
        self._current_task_turns = 0
    
    def end_task(self) -> None:
        """结束当前任务"""
        if self._task_start_time:
            duration = time.time() - self._task_start_time
            if self._current_task_turns > 0:
                # 更新平均
                prev = self.stats.avg_turns_per_task
                count = self.stats.successful_iterations
                self.stats.avg_turns_per_task = (prev * count + self._current_task_turns) / (count + 1)
                self.stats.successful_iterations += 1
            self._task_start_time = None
            self._current_task_turns = 0
    
    def get_stats(self) -> BudgetStats:
        """获取统计信息"""
        return self.stats
    
    def get_usage_summary(self) -> str:
        """获取使用摘要"""
        remaining = self.max_total - self._used
        pct = remaining / self.max_total * 100
        level = self.get_warning_level()
        
        lines = [
            f"Iteration Budget: {remaining}/{self.max_total} ({pct:.1f}% remaining)",
            f"Warning Level: {level.value}",
            f"Total Iterations: {self.stats.total_iterations}",
            f"Forced Terminations: {self.stats.forced_terminations}",
            f"Compression Triggered: {self.stats.compression_triggered}",
        ]
        
        if self.stats.tool_usage:
            lines.append("\nTop Tools:")
            sorted_tools = sorted(self.stats.tool_usage.items(), key=lambda x: -x[1])[:5]
            for tool, count in sorted_tools:
                lines.append(f"  {tool}: {count}")
        
        return "\n".join(lines)
    
    def reset(self) -> None:
        """重置预算"""
        self._used = 0
        self._history.clear()
        self.stats = BudgetStats()
        self._tool_budgets.clear()
        self._task_start_time = None
        self._current_task_turns = 0


# 向后兼容：保持原有IterationBudget接口
class IterationBudget(EnhancedIterationBudget):
    """
    兼容层：保持原有IterationBudget接口
    
    向后兼容原有的 IterationBudget 类，
    新代码应使用 EnhancedIterationBudget。
    """
    
    def __init__(self, max_total: int = 90):
        super().__init__(max_total=max_total, track_history=False)


# 全局实例
_global_budget: Optional[EnhancedIterationBudget] = None


def get_global_budget() -> EnhancedIterationBudget:
    """获取全局预算实例"""
    global _global_budget
    if _global_budget is None:
        _global_budget = EnhancedIterationBudget()
    return _global_budget


def set_global_budget(budget: EnhancedIterationBudget) -> None:
    """设置全局预算实例"""
    global _global_budget
    _global_budget = budget
