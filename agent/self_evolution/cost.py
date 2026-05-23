"""
EvolutionCost — JEPA Cost Module for Code Architecture Domain

物理世界: IC(能量守恒/不穿透) + TC(距目标距离)
代码世界: IC(不改agent核心/不破坏tier0) + TC(改动行数/影响面最小)

IC 是硬约束（违反任一→+∞），TC 是软优化（越小越好）。

EV-VOE12: 继承自 cost_framework.AbstractCostModule（统一 IC+TC 框架）
"""

from typing import Dict, List, Optional, Any

from .state_encoder import StateEncoder, CodebaseState, DependencyNode, PROTECTED_FILES
from .cost_framework import AbstractCostModule, CostResult


class EvolutionCost(AbstractCostModule):
    """
    JEPA Cost Module: 评估代码改动的风险

    IC (Intrinsic Cost — 硬编码，不可学习):
        - agent_core_violation: 改了 agent/ 核心文件 → IC = +∞
        - gateway_violation: 改了 gateway 接口文件 → IC = +∞
        - tier0_break: 可能破坏 tier0 基线 → IC = +∞
        - tool_registry_break: 工具注册链断裂 → IC = +∞

    TC (Task Cost — 可变的，每任务不同):
        - change_size: 改动行数
        - blast_radius: 受影响文件数（传递闭包）
        - constraint_risk: 触及约束边界的风险
    """

    # ── IC 硬约束定义 ──
    # 文件列表来自 state_encoder.PROTECTED_FILES（单源），
    # 此处只定义每组的 severity + description 元数据。
    # tier0_baseline 是动态的（运行时检测），不在 PROTECTED_FILES 中。
    IC_RULES = {
        "agent_core": {
            "severity": float("inf"),
            "description": "Agent核心文件，改动可能导致推理循环断裂",
        },
        "gateway_interface": {
            "severity": float("inf"),
            "description": "Gateway接口文件，改动后飞书/Message通道可能断裂",
        },
        "tool_registry": {
            "severity": float("inf"),
            "description": "工具注册链，改动后所有工具调用可能失败",
        },
        "tier0_baseline": {
            "severity": float("inf"),
            "description": "tier0基线失败时阻止任何改动（先修基线再改代码）",
        },
    }

    def __init__(self, encoder: Optional[StateEncoder] = None):
        self.encoder = encoder or StateEncoder()
        self._tc_weights = {
            "change_size": 0.01,       # 每行改动 = 0.01
            "blast_radius": 0.5,        # 每个受影响文件 = 0.5
            "constraint_risk": 5.0,     # 触及约束边界 = 5.0
        }

    def evaluate(
        self,
        proposed_changes: List[str],
        estimated_lines: int = 0,
    ) -> CostResult:
        """
        评估一次拟议改动的代价

        Args:
            proposed_changes: 拟改动的文件列表 (相对 agent/ 路径)
            estimated_lines: 预估改动行数

        Returns:
            CostResult with detailed breakdown
        """
        state = self.encoder.encode()
        ic_cost, ic_violations = self._compute_ic(proposed_changes)
        tc_cost, tc_breakdown = self._compute_tc(proposed_changes, estimated_lines, state)

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

    def is_safe(self, proposed_changes: List[str]) -> bool:
        """快速安全检查：拟改文件是否在约束内"""
        result = self.evaluate(proposed_changes)
        return result.passed

    # ── 内部 ──

    def _compute_ic(self, proposed_changes: List[str]) -> tuple:
        """计算硬约束代价。文件列表来自 encoder.constraint_map（单源 PROTECTED_FILES）"""
        violations = []
        state = self.encoder.encode()
        constraint_map = state.constraint_map  # 单源约束

        # 静态文件列表检查
        for fpath in proposed_changes:
            for rule_name, rule_def in self.IC_RULES.items():
                if rule_name == "tier0_baseline":
                    continue  # tier0 在下面单独动态检查
                # 从 constraint_map（单源）查文件列表，而非 IC_RULES
                protected = constraint_map.get(rule_name, [])
                if fpath in protected:
                    violations.append(
                        f"[{rule_name}] {fpath}: {rule_def['description']}"
                    )

        # 动态 tier0 检查：如果基线失败，阻止任何改动
        tier0_status = state.tier0_status
        if isinstance(tier0_status, dict) and tier0_status.get("status") != "not_run":
            exit_code = tier0_status.get("exit_code", -1)
            if exit_code != 0:
                violations.append(
                    f"[tier0_baseline] tier0 exit_code={exit_code}: "
                    f"{self.IC_RULES['tier0_baseline']['description']}"
                )

        ic_cost = float("inf") if violations else 0.0
        return ic_cost, violations

    def _compute_tc(
        self, proposed_changes: List[str], estimated_lines: int, state: CodebaseState
    ) -> tuple:
        """计算软目标代价"""
        breakdown = {}

        # change_size: 改动行数
        # 保守估计——实际改动量通常远小于文件总行数
        if estimated_lines:
            lines = estimated_lines
        else:
            total_file_lines = sum(
                state.files.get(f, DependencyNode(file_path=f)).n_lines
                for f in proposed_changes
            )
            lines = min(10, total_file_lines * 0.05)  # 保守: 5% 或最多10行
        breakdown["change_size"] = lines * self._tc_weights["change_size"]

        # blast_radius: 受影响的文件数（传递闭包）
        all_affected = set()
        for fpath in proposed_changes:
            all_affected.update(self.encoder.get_dependents(fpath))
        breakdown["blast_radius"] = len(all_affected) * self._tc_weights["blast_radius"]

        # constraint_risk: 拟改文件的高扇出程度
        max_fan_out = max(
            (self.encoder.get_fan_out(f) for f in proposed_changes), default=0
        )
        breakdown["constraint_risk"] = min(max_fan_out * 0.1, self._tc_weights["constraint_risk"])

        tc_cost = sum(breakdown.values())
        return tc_cost, breakdown
