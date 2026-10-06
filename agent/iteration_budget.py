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
import os
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set

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


# ══════════════════════════════════════════════════════════════════════════
# B3 防截断（2026-10-06 · 刘哥派单）：轮次预算的「产出侧」闸门
#   治「轮次用满仍未落盘 ⇒ 产出全丢」（2026-10-06 18:21 实证：120 轮·841s·产出全丢）
#   判据单一真源：empty_run_gate.deliverable_written（run 级，非 turn 级）
# ══════════════════════════════════════════════════════════════════════════
B3_PROD_CHECKPOINT = True

DEFAULT_CHECKPOINT_RATIO = 0.8
DEFAULT_HANDOFF_TURNS = 60


def b3_enabled() -> bool:
    return os.environ.get("MIMIR_B3_GUARD", "1").strip().lower() not in ("0", "false", "no", "off")


def checkpoint_ratio() -> float:
    try:
        return min(1.0, max(0.0, float(os.environ.get("MIMIR_CHECKPOINT_RATIO", "0.8"))))
    except Exception:
        return DEFAULT_CHECKPOINT_RATIO


def handoff_turns() -> int:
    try:
        return max(0, int(os.environ.get("MIMIR_HANDOFF_TURNS", "60")))
    except Exception:
        return DEFAULT_HANDOFF_TURNS


def half_segment_threshold(max_turns: int, ratio: Optional[float] = None) -> int:
    """强制半段阈值 = ceil(ratio * max_turns)（钳在 [1, max_turns]）。"""
    import math
    r = checkpoint_ratio() if ratio is None else min(1.0, max(0.0, float(ratio)))
    return max(1, min(int(max_turns or 1), int(math.ceil(r * int(max_turns or 1)))))


def build_half_segment_directive(turn: int, max_turns: int, threshold: int) -> str:
    """规则①：轮次用满 ~80% 仍未落盘 ⇒ 强制先写「半段」再继续。"""
    return (
        f"【B3·防截断】轮次已用 {turn}/{max_turns}（≥{threshold} = 80% 阈值）且本 run **交付物未写** —— "
        "本轮**必须**先落盘「半段」再继续。半段定义（两件，缺一不算）："
        "① 已完成的证据读数（每行 = 可复现命令 + 实测数字）；"
        "② 明确未闭项清单（`- [ ] …` 逐条）。"
        "写完才允许继续调用工具；禁在零落盘状态下继续只读推进。"
    )


def build_handoff_directive(turn: int, max_turns: int) -> str:
    """规则②：>60 轮大活 ⇒ 先落盘交棒（分段），禁止一口气跑到轮次耗尽。"""
    return (
        f"【B3·防截断·交棒】本 run 已到第 {turn} 轮（>{handoff_turns()} 轮 = 大活）——**先落盘交棒再继续**："
        "把进度落成「半段 + 交棒清单」（已完成读数 / 未闭项 / 下一段第一件事），"
        "并按 AGENTS §8.4 带两字段（`重跑命令:` / `复算数字:`）。"
        f"禁在无落盘状态下跑到 {max_turns} 轮耗尽（120 轮产出全丢事故的充要条件）。"
    )


class ProductionCheckpointPolicy:
    """轮次预算 × 产出侧的幂等闸门（无 IO；has_written 可注入 ⇒ 可离线测）。

    接线点：core_loop._model_call_adapter（每轮恰好调用一次）⇒ tick()；返回指令则追加为
    最后一条 user 消息（与既有 nudge/闸门同形态，序列合法）。
    """

    def __init__(self, max_turns: int, ratio: Optional[float] = None,
                 handoff: Optional[int] = None, task_id: str = "",
                 has_written=None) -> None:
        self.max_turns = int(max_turns or 1)
        self.half_threshold = half_segment_threshold(self.max_turns, ratio)
        self.handoff = handoff_turns() if handoff is None else int(handoff)
        self.task_id = task_id or "run"
        self._has_written = has_written
        self.half_fired = False
        self.handoff_fired = False
        self.decisions: List[Dict[str, Any]] = []

    def _written(self, messages) -> bool:
        if self._has_written is not None:
            try:
                return bool(self._has_written(messages))
            except Exception:
                return False
        try:
            from .empty_run_gate import deliverable_written
        except Exception:  # pragma: no cover - 脚本式导入
            from empty_run_gate import deliverable_written  # type: ignore
        try:
            return bool(deliverable_written(messages))
        except Exception:
            return False

    def tick(self, messages, turn: int) -> Optional[str]:
        """每轮调用一次。返回 None = 无指令；否则返回注入用的指令文本（幂等：每阈值仅一次）。"""
        if not b3_enabled():
            return None
        t = int(turn or 0)
        written = self._written(messages)
        if (not self.half_fired) and t >= self.half_threshold and not written:
            self.half_fired = True
            self.decisions.append({"kind": "half_segment", "turn": t,
                                   "threshold": self.half_threshold})
            return build_half_segment_directive(t, self.max_turns, self.half_threshold)
        if (not self.handoff_fired) and self.handoff > 0 and self.max_turns > self.handoff \
                and t >= self.handoff:
            self.handoff_fired = True
            self.decisions.append({"kind": "handoff", "turn": t, "threshold": self.handoff})
            return build_handoff_directive(t, self.max_turns)
        return None


def _b3_half_dir() -> str:
    home = os.environ.get("MIMIR_AETHER_HOME") or os.path.expanduser("~/.mimiraether")
    return os.path.join(home, "data", "half_drafts")


def _b3_safe_id(task_id: str) -> str:
    import re as _re
    return _re.sub(r"[^A-Za-z0-9._-]", "_", task_id or "run")[:40]


def write_framework_half_segment(task_id: str, turn: int, max_turns: int, reason: str,
                                 messages, last_assistant: str = "",
                                 out_dir: Optional[str] = None) -> Dict[str, Any]:
    """收尾兜底：轮次耗尽仍零落盘 ⇒ 框架代写**半段**（内容 = 已确证读数 + 未闭项 + 半句原文）。

    幂等：同一 (task_id, reason) 已存在则不重复写（返回 already_written）。
    返回 {'written': bool, 'path': str, 'chars': int, 'reason': str}
    """
    out = {"written": False, "path": "", "chars": 0, "reason": ""}
    d = out_dir or _b3_half_dir()
    try:
        os.makedirs(d, exist_ok=True)
    except Exception as e:
        out["reason"] = f"mkdir_failed:{e}"
        return out
    path = os.path.join(d, f"{_b3_safe_id(task_id)}-{_b3_safe_id(reason)}.md")
    if os.path.exists(path):
        out.update(path=path, reason="already_written",
                   chars=os.path.getsize(path))
        return out
    calls: List[str] = []
    for m in (messages or []):
        if not isinstance(m, dict) or m.get("role") != "assistant":
            continue
        for tc in (m.get("tool_calls") or []):
            try:
                fn = tc.get("function") or {}
                nm = fn.get("name") or tc.get("name") or "?"
                ag = str(fn.get("arguments") or "")[:120]
            except Exception:
                nm, ag = "?", ""
            calls.append(f"- `{nm}` {ag}".rstrip())
    tail = (last_assistant or "").strip()[:4000]
    body = (
        f"# 【Mimir · 半段（框架代写 · B3 防截断）】\n"
        f"<!-- run={_b3_safe_id(task_id)} turn={turn}/{max_turns} reason={reason} "
        f"written=framework -->\n\n"
        f"**本 run 以 `{reason}` 退出且交付物未写** ⇒ 此文件为框架代写的最小半段，"
        f"保证「产出为零」不成立；**不等于任务完成**。\n\n"
        f"## 1. 已确证读数（本 run 实际发生的工具调用，末 {max(0, len(calls))} 条）\n"
        + ("\n".join(calls[-40:]) if calls else "(本 run 无工具调用)") + "\n\n"
        f"## 2. 未收尾的半句原文（末条 assistant 正文，截断至 4000 字符）\n\n"
        + (tail if tail else "(空)") + "\n\n"
        f"## 3. 未闭项清单\n"
        f"- [ ] 任务本体未收尾：以上读数未落成交付物\n"
        f"- [ ] 下一段第一件事：读本文件 + 续作（拆小任务重发）\n"
        f"- [ ] 复盘：本 run 为何跑到 {turn} 轮仍未落盘（`{reason}`）\n"
    )
    try:
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(body)
    except Exception as e:
        out["reason"] = f"write_failed:{e}"
        return out
    out.update(written=True, path=path, chars=len(body), reason="written")
    return out
