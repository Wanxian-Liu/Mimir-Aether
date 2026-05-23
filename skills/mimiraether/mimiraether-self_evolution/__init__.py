"""
MimirAether Self Evolution Skill
集成三环闭环引擎 (已从 mimicore 提取)
"""

import sys
from mimir_constants import get_mimir_home

# 添加项目路径（运行时解析，支持 MIMIR_AETHER_HOME / HERMES_HOME 覆盖）
PROJECT_ROOT = get_mimir_home()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from .three_ring_architecture import ThreeRingClosedLoop


class SelfEvolutionSkill:
    """MimirAether 自我进化技能

    基于三环闭环架构（MonitorRing → DecisionRing → ExecutionRing），
    实现系统自监控、差距分析、改进执行与效果验证。
    """

    def __init__(self):
        self.three_ring = ThreeRingClosedLoop()
        self._initialized = True

    async def collect_metrics(self) -> dict:
        """收集系统指标"""
        metrics = await self.three_ring.monitor.observe()
        return metrics

    async def analyze_gaps(self, metrics: dict) -> dict:
        """分析差距"""
        anomalies = await self.three_ring.monitor.detect_anomalies(metrics)

        if not anomalies:
            return {"gaps": [], "priority_gap": None}

        root_cause = await self.three_ring.decision.analyze_root_cause(anomalies)
        strategies = await self.three_ring.decision.generate_strategies(root_cause)

        return {
            "root_cause": root_cause,
            "strategies": strategies,
            "anomaly_count": len(anomalies),
        }

    async def execute_improvement(self, plan: dict) -> dict:
        """执行改进"""
        strategies = plan.get("strategies", [])
        if not strategies:
            return {"status": "no_strategy"}

        decision = await self.three_ring.decision.select_best_strategy(strategies)
        execution = await self.three_ring.execution.execute(decision, {})

        return {
            "decision": decision.__dict__,
            "execution": execution.__dict__,
        }

    async def verify_result(self, before: dict, after: dict, execution) -> dict:
        """验证结果"""
        verified = await self.three_ring.execution.verify(execution, {})
        return {
            "verification_passed": verified,
            "effectiveness": execution.effectiveness_score,
        }

    async def run_cycle(self) -> dict:
        """执行完整进化周期"""
        metrics_before = await self.collect_metrics()
        gap_analysis = await self.analyze_gaps(metrics_before)

        if not gap_analysis.get("gaps"):
            return {"status": "healthy", "metrics": metrics_before}

        improvement = await self.execute_improvement(gap_analysis)
        metrics_after = await self.collect_metrics()

        execution = improvement["execution"]
        verification = await self.verify_result(
            metrics_before, metrics_after, execution
        )

        return {
            "status": "completed" if verification["verification_passed"] else "retry_needed",
            "before": metrics_before,
            "after": metrics_after,
            "gap_analysis": gap_analysis,
            "improvement": improvement,
            "verification": verification,
        }


async def collect_metrics() -> dict:
    """收集系统指标"""
    skill = SelfEvolutionSkill()
    return await skill.collect_metrics()


async def analyze_gaps(metrics: dict) -> dict:
    """分析差距"""
    skill = SelfEvolutionSkill()
    return await skill.analyze_gaps(metrics)


async def execute_improvement(plan: dict) -> dict:
    """执行改进"""
    skill = SelfEvolutionSkill()
    return await skill.execute_improvement(plan)


async def verify_result(before: dict, after: dict, execution) -> dict:
    """验证结果"""
    skill = SelfEvolutionSkill()
    return await skill.verify_result(before, after, execution)


async def run_evolution_cycle() -> dict:
    """执行完整进化周期"""
    skill = SelfEvolutionSkill()
    return await skill.run_cycle()


__all__ = [
    "SelfEvolutionSkill",
    "collect_metrics",
    "analyze_gaps",
    "execute_improvement",
    "verify_result",
    "run_evolution_cycle",
]
