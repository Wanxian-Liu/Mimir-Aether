# [DORMANT] mimiraether-physics-reasoner

**沉寂时间**: 2026-07-23T06:18:46.627318+00:00
**原始分类**: mimiraether
**描述**: Mimir 物理推理助手 — 路线 1（力学核心求解器）。 自然语言 → 公式匹配 → SymPy 推导 → NumPy 求解 → 自然语言回报。 基于杨立昆 JEPA（不预测像素，预测抽象表征）和李飞飞空间智能（物理接地）。 CPU only，零新增依赖，不改 agent/gateway。

**触发阈值**: 60天未触碰

---

## 技能要点

# Mimir 物理推理助手（力学核心）

## 覆盖范围
- 运动学：匀加速、自由落体、抛体、斜面
- 动力学：牛顿第二定律、摩擦力、弹簧、单摆
- 能量/动量：动能定理、动量守恒、弹性/非弹性碰撞
- 公式数：20 个核心公式

## 使用方法
```python
from mimiraether_physics_reasoner.solver import PhysicsSolver, PhysicsQuery
from mimiraether_physics_reasoner.skill_migrator import SkillMigrator

solver = PhysicsSolver()
result = solver.solve(PhysicsQuery(
    domain="kinematics",
    given={"height": 10, "g": 9.8},
    target="velocity",
))
# → Solution(result=14.0, unit="m/s", steps=[...])
```

## 验收：5 题全对
1. 自由落体速度 ✅ v=14.0 m/s
2. 斜面加速度 ✅ a=3.20 m/s²
3. 弹性碰撞 ✅ v1_after=1.0 m/s
4. 弹簧周期 ✅ T=0.314 s
5. 抛体水平射程 ✅ R=40.82 m

## 架构依据
- LeCun (2022) "A Path Towards Autonomous Machine Intelligence" — JEPA 架构、Mode-1/2 迁移、Intrinsic Cost
- Li (2024) "World Labs" — 空间智能、物理接地、"黑暗中的词匠"

---

> 此胶囊由 Skill Curator 自动生成。原始技能已移入 .dormant/。
> 调用 `skill_view("mimiraether-physics-reasoner")` 即可自动唤醒。
