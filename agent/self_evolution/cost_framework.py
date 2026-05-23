"""
统一 Cost 框架（EV-VOE11）：JEPA IC+TC 两段式评估的公共基类

消除物理 WM (cost_module.py) 和代码 WM (cost.py) 的重复实现。
未来任何新领域（运维/对话/安全）只需继承基类并注册 IC/TC 规则。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional


@dataclass
class CostResult:
    """代价评估结果 — 跨领域通用"""
    total: float                    # C(s) = IC + TC
    ic_cost: float                  # 硬约束代价 (0 或 +inf)
    tc_cost: float                  # 软目标代价
    ic_violations: List[str] = field(default_factory=list)
    tc_breakdown: Dict[str, float] = field(default_factory=dict)
    passed: bool = False

    def is_valid(self) -> bool:
        """是否通过 IC 硬约束"""
        return self.ic_cost < float("inf") and not self.ic_violations


class AbstractCostModule(ABC):
    """
    JEPA Cost 模块公共基类。

    物理 WM 和代码 WM 共享同一模式：
      C(s) = IC(s) + TC(s, goal)

    子类只需实现 _compute_ic(s) 和 _compute_tc(s, goal, **kwargs)。
    """

    _name: str = "AbstractCost"

    # ── 模板方法 ──

    def evaluate(self, state: Any, goal: Optional[Any] = None, **kwargs) -> CostResult:
        """
        评估状态 s 的代价。

        Args:
            state: 领域特定的状态编码（物理WM: list[Bodies], 代码WM: CodebaseState）
            goal: 可选的目标状态
            **kwargs: 领域特定参数

        Returns:
            CostResult(ic, tc, total, violation details)
        """
        ic_cost, ic_violations = self._compute_ic(state, **kwargs)
        tc_cost, tc_breakdown = self._compute_tc(state, goal, **kwargs)

        total = ic_cost + tc_cost
        passed = ic_cost == 0.0 and not ic_violations

        return CostResult(
            total=total,
            ic_cost=ic_cost,
            tc_cost=tc_cost,
            ic_violations=ic_violations,
            tc_breakdown=tc_breakdown,
            passed=passed,
        )

    def is_safe(self, state: Any, **kwargs) -> bool:
        """快速安全门：只检查 IC 硬约束"""
        return self.evaluate(state, **kwargs).passed

    # ── 子类必须实现 ──

    @abstractmethod
    def _compute_ic(self, state: Any, **kwargs) -> tuple[float, List[str]]:
        """
        计算 IC（Intrinsic Cost）——不可变的物理/架构约束。

        Returns:
            (ic_cost, violations):
                - 无违反: (0.0, [])
                - 轻微违反: (>0, [reasons])
                - 致命违反: (float('inf'), [reasons])
        """
        ...

    @abstractmethod
    def _compute_tc(self, state: Any, goal: Optional[Any], **kwargs) -> tuple[float, Dict[str, float]]:
        """
        计算 TC（Task Cost）——任务特定的目标距离。

        Returns:
            (tc_cost, breakdown):
                tc_cost: 加权后的总 TC
                breakdown: 各维度的原始分数
        """
        ...

    # ── 可选扩展 ──

    def describe(self, result: CostResult) -> str:
        """人类可读的代价描述"""
        parts = []
        if result.ic_cost > 0:
            if result.ic_cost == float("inf"):
                parts.append("IC: BLOCKED (硬约束违反)")
            else:
                parts.append(f"IC: {result.ic_cost:.2f}")
        else:
            parts.append("IC: PASS")

        parts.append(f"TC: {result.tc_cost:.3f}")
        if result.ic_violations:
            parts.append(f"Violations: {result.ic_violations}")

        parts.append(f"Total: {result.total:.3f}")
        return " | ".join(parts)
