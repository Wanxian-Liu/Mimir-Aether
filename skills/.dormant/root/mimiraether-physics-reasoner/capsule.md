# [DORMANT] mimiraether-physics-reasoner

**沉寂时间**: 2026-07-23T06:24:31.732403+00:00
**原始分类**: root
**描述**: Mimir 物理推理助手 — 路线 1（力学核心求解器）。 自然语言 → 公式匹配 → SymPy 推导 → NumPy 求解 → 自然语言回报。 基于杨立昆 JEPA（不预测像素，预测抽象表征）和李飞飞空间智能（物理接地）。 CPU only，零新增依赖，不改 agent/gateway。

**触发阈值**: 60天未触碰

---

## 技能要点

# Mimir 物理推理助手（力学核心）

## 核心原则

1. **方程空间推理** — LLM 只做入口路由和出口解释，中间计算在 SymPy/NumPy 方程空间
2. **层级化子目标分解** — Level 2（问题类型）→ Level 1（公式选择）→ Level 0（数值求解），可回溯
3. **不生成像素** — 物理世界模型 = 数学公式 + 数值方法，不是 3D 渲染
4. **SkillMigrator** — Mode-2（慢推理）→ Mode-1（快查表）自动迁移，越用越快

## 覆盖范围

- **运动学**：匀加速、自由落体、抛体、斜面
- **动力学**：牛顿第二定律、摩擦力、弹簧、单摆
- **能量/动量**：动能定理、动量守恒、弹性/非弹性碰撞
- **公式数**：~20 个核心公式

## 使用方法

```python
from formulas.mechanics import MECHANICS_FORMULAS, match_formula
from solver import PhysicsSolver

solver = PhysicsSolver(MECHANICS_FORMULAS)
solution = solver.solve(
    domain="mechanics",
    given={"mass": 5, "height": 10, "g": 9.8},
    target="velocity"
)
# → Solution(result=14.0, unit="m/s", steps=[...])
```

## 验收标准

5 道经典力学题全部正确：
1. 自由落体速度
2. 斜面加速度
3. 弹性碰撞末速度
4. 弹簧周期
5. 抛体水平射程

## 架构依据

- LeCun (2022) "A Path Towards Autonomous Machine Intelligence" — JEPA 架构、Mode-1/2 迁移、Intrinsic Cost
- Li (2024) "World Labs" — 空间智能、物理接地、"黑暗中的词匠"

---

> 此胶囊由 Skill Curator 自动生成。原始技能已移入 .dormant/。
> 调用 `skill_view("mimiraether-physics-reasoner")` 即可自动唤醒。
