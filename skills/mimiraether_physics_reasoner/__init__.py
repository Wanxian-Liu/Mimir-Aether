"""Mimir 物理推理助手 — 路线 1 力学核心求解器

基于：
  - 杨立昆 JEPA（不预测像素，预测抽象表征）
  - 李飞飞空间智能（物理接地，"黑暗中的词匠"）

使用：
  from .solver import PhysicsSolver, PhysicsQuery, Solution
  from .formulas.mechanics import MECHANICS_FORMULAS, match_formula
  from .skill_migrator import SkillMigrator

  solver = PhysicsSolver()
  migrator = SkillMigrator()

  # System 1 快查表
  cached = migrator.lookup("kinematics", "velocity", {"height": 10, "g": 9.8})
  if cached:
      return cached.result, cached.unit

  # System 2 完整推导
  result = solver.solve(PhysicsQuery(
      domain="kinematics",
      given={"height": 10, "g": 9.8},
      target="velocity",
  ))

  # 自动迁移（≥3 次后）
  migrator.on_solve("kinematics", "velocity", {"height": 10, "g": 9.8},
                     result.result, result.unit,
                     result.formula_used, result.steps)
"""

from .solver import PhysicsSolver, PhysicsQuery, Solution
from .skill_migrator import SkillMigrator, CannedSolution

__all__ = [
    "PhysicsSolver",
    "PhysicsQuery",
    "Solution",
    "SkillMigrator",
    "CannedSolution",
]
