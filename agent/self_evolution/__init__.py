"""
MimirAether Self-Evolution Engine — JEPA Framework Migration

基于世界模型颗粒0-5验证的JEPA框架，从物理状态空间迁移到代码架构状态空间。

四组件:
- StateEncoder: agent/ 文件 → 依赖图 + 约束图 + tier0状态
- EvolutionCost: IC(不改agent核心约束) + TC(改动量最小化)
- SafestPathPlanner: 搜索最小风险重构路径
- EvolutionMemory: 过去演化结果 → 未来决策参考
- SelfEvolutionEngine: JEPA闭环 (编码→预测→代价→规划→记忆)

与Mimicore的关系: 本模块不依赖mimicore/evolve/，使用已验证的JEPA框架重写。
"""

from .state_encoder import StateEncoder, CodebaseState, DependencyNode
from .cost import EvolutionCost, CostResult
from .memory import EvolutionMemory, EvolutionRecord
from .planner import SafestPathPlanner, PlanResult
from .engine import SelfEvolutionEngine

__all__ = [
    "StateEncoder", "CodebaseState", "DependencyNode",
    "EvolutionCost", "CostResult",
    "EvolutionMemory", "EvolutionRecord",
    "SafestPathPlanner", "PlanResult",
    "SelfEvolutionEngine",
    "analyze",  # 便捷集成点
]
__version__ = "0.2.0"  # tier0真实读取 + 约束双源统一 + analyze集成


# ── 便捷集成点：外部可直接调用，不依赖 agent loop ──

def analyze(candidate_files: list, force_refresh: bool = False) -> dict:
    """
    JEPA 闭环分析入口 — 供 Mimir playbook / CLI / 外部脚本调用。
    
    不改任何文件，只读审计。
    
    Args:
        candidate_files: 拟改动的 agent/ 文件列表
        force_refresh: 是否强制刷新缓存
    
    Returns:
        {"passed": bool, "violations": [...], "safe_files": [...], 
         "total_cost": float, "tier0": dict, "plan": dict}
    """
    engine = SelfEvolutionEngine()
    result = engine.analyze(candidate_files)
    return {
        "passed": len(result["plan"]["ic_violations"]) == 0,
        "violations": result["plan"]["ic_violations"],
        "safe_files": result["plan"]["safe_files"],
        "total_cost": result["plan"]["total_cost"],
        "tier0": result["state"].get("tier0_status", {}),
        "plan": {
            "recommended_order": result["plan"]["recommended_order"],
            "notes": result["plan"]["notes"],
        },
    }
