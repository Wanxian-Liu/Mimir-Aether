"""
SafestPathPlanner — JEPA Planner for Code Architecture Domain

物理世界: CEM 搜索最优动作序列（力×时间步）
代码世界: 搜索最安全的文件改动序列

核心：给定一组待改动的文件，按代价排序，找到最小风险路径。
"""

import time
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

from .state_encoder import StateEncoder, CodebaseState
from .cost import EvolutionCost, CostResult
from .memory import EvolutionMemory, EvolutionRecord


@dataclass
class PlanResult:
    """规划结果"""
    plan_id: str
    timestamp: float
    recommended_order: List[str]        # 建议的改动顺序（最安全→最危险）
    cost_per_file: Dict[str, CostResult]  # 每个文件的代价评估
    total_cost: float
    ic_violations: List[str]            # 绝对不可改的文件
    safe_files: List[str]               # 可以安全改动的文件
    notes: List[str] = field(default_factory=list)


class SafestPathPlanner:
    """
    JEPA Planner: 最小风险重构路径搜索

    不像物理CEM那个随机搜索动作空间，
    这里对确定性领域（代码依赖图）用精确排序。

    算法：
    1. 对每个候选文件评估 IC + TC
    2. IC=+∞ 的文件 → 标记为不可改
    3. 剩余文件按 TC 升序排列
    4. 验证顺序：改了前面的文件不会让后面的文件评估失效
    """

    def __init__(
        self,
        encoder: Optional[StateEncoder] = None,
        cost: Optional[EvolutionCost] = None,
        memory: Optional[EvolutionMemory] = None,
    ):
        self.encoder = encoder or StateEncoder()
        self.cost = cost or EvolutionCost(self.encoder)
        self.memory = memory or EvolutionMemory()

    def plan(
        self,
        candidate_files: List[str],
        estimated_lines_per_file: Optional[Dict[str, int]] = None,
        max_risk_files: int = 10,
    ) -> PlanResult:
        """
        规划最安全的改动顺序

        Args:
            candidate_files: 候选改动文件列表
            estimated_lines_per_file: 每个文件的预估改动行数
            max_risk_files: 最多输出多少个安全文件

        Returns:
            PlanResult with ordered recommendations
        """
        estimated_lines_per_file = estimated_lines_per_file or {}
        cost_per_file: Dict[str, CostResult] = {}
        safe_files: List[str] = []
        ic_violations: List[str] = []
        notes: List[str] = []

        # 1. 评估每个文件
        for fpath in candidate_files:
            est_lines = estimated_lines_per_file.get(fpath, 0)
            result = self.cost.evaluate([fpath], est_lines)
            cost_per_file[fpath] = result

            if result.passed:
                safe_files.append(fpath)
            else:
                ic_violations.extend(result.ic_violations)

        # 2. 安全文件按 TC 排序
        safe_files.sort(key=lambda f: cost_per_file[f].tc_cost)

        # 3. 验证顺序：改了第i个文件后的冲击面是否包含第i+1个文件
        # (简化版：如果排在前面的文件被排在后面的文件依赖，调整顺序)
        ordered = self._validate_order(safe_files, cost_per_file)

        # 4. 添加记忆参考
        for fpath in ordered[:5]:
            history = self.memory.query_by_file(fpath, limit=1)
            if history:
                last = history[0]
                notes.append(
                    f"{fpath}: 上次改动于 {last.outcome} "
                    f"(tier0={last.tier0_result or 'N/A'})"
                )

        # 5. 计算总代价
        total_cost = sum(cost_per_file[f].tc_cost for f in ordered)

        return PlanResult(
            plan_id=f"plan_{int(time.time() * 1000)}",
            timestamp=time.time(),
            recommended_order=ordered[:max_risk_files],
            cost_per_file=cost_per_file,
            total_cost=total_cost,
            ic_violations=ic_violations,
            safe_files=ordered[:max_risk_files],
            notes=notes,
        )

    def plan_single(self, file_path: str, estimated_lines: int = 0) -> PlanResult:
        """单文件快速规划"""
        return self.plan([file_path], {file_path: estimated_lines})

    # ── 内部 ──

    def _validate_order(
        self,
        safe_files: List[str],
        cost_per_file: Dict[str, CostResult],
    ) -> List[str]:
        """验证改动顺序的依赖一致性"""
        if len(safe_files) <= 1:
            return list(safe_files)

        # 检查：如果 A 被 B 依赖（B imports A），A 应该排在 B 前面
        state = self.encoder.encode()
        ordered = []

        # 构建 safe_files 间的依赖关系
        deps: Dict[str, set] = {}
        for f in safe_files:
            callers = state.call_graph.get(f, [])
            deps[f] = {c for c in callers if c in safe_files}

        # 拓扑排序
        remaining = set(safe_files)
        while remaining:
            # 找无依赖或依赖已处理的文件
            ready = {f for f in remaining if not (deps.get(f, set()) & remaining)}
            if not ready:
                # 循环依赖：按 TC 排序
                remaining_list = sorted(remaining, key=lambda f: cost_per_file[f].tc_cost)
                ordered.extend(remaining_list)
                break
            ordered.extend(sorted(ready, key=lambda f: cost_per_file[f].tc_cost))
            remaining -= ready

        return ordered
