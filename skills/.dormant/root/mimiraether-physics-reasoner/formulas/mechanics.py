"""力学公式库 — ~20 个核心公式

覆盖：运动学 / 动力学 / 能量 / 动量 / 振动
每个公式含：名称、表达式、领域、约束条件、量纲验证规则
"""

from dataclasses import dataclass, field
from typing import Any, Optional

# ── 可用的物理常量符号 ──────────────────────────────
# 求解器会自动注入这些到 SymPy 命名空间
# g, m, h, v, v0, a, t, F, mu, N, theta, k, x, p, E, W, omega, T, f, L, I, R, V

@dataclass
class Formula:
    """物理公式"""
    name: str                           # 唯一标识，如 "free_fall_velocity"
    expression: str                     # LaTeX 风格表达式，如 "v = sqrt(2*g*h)"
    domain: str                         # "kinematics" / "dynamics" / "energy" / "momentum"
    description: str                    # 中文描述
    given: list[str]                    # 需要的已知量，如 ["h", "g"]
    target: str                         # 求解目标变量，如 "v"
    constraints: list[str] = field(default_factory=list)  # 约束条件，如 ["h >= 0"]
    variants: dict[str, str] = field(default_factory=dict)  # 变形公式 {target: expression}


# ══════════════════════════════════════════════════════
# 一、运动学 (Kinematics) — 6 公式
# ══════════════════════════════════════════════════════

MECHANICS_FORMULAS = [
    # ── 1. 匀加速速度公式 ──
    Formula(
        name="uniform_accel_velocity",
        expression="v = v0 + a*t",
        domain="kinematics",
        description="匀加速运动速度公式",
        given=["v0", "a", "t"],
        target="v",
        variants={
            "v0": "v0 = v - a*t",
            "a": "a = (v - v0)/t",
            "t": "t = (v - v0)/a",
        },
    ),

    # ── 2. 匀加速位移公式 ──
    Formula(
        name="uniform_accel_displacement",
        expression="x = v0*t + 0.5*a*t**2",
        domain="kinematics",
        description="匀加速运动位移公式",
        given=["v0", "a", "t"],
        target="x",
        variants={
            "v0": "v0 = (x - 0.5*a*t**2)/t",
            "a": "a = 2*(x - v0*t)/t**2",
        },
    ),

    # ── 3. 速度-位移关系 ──
    Formula(
        name="velocity_displacement",
        expression="v**2 = v0**2 + 2*a*x",
        domain="kinematics",
        description="速度平方与位移关系（消去时间）",
        given=["v0", "a", "x"],
        target="v",
        constraints=["v0**2 + 2*a*x >= 0"],
        variants={
            "v0": "v0 = sqrt(v**2 - 2*a*x)",
            "a": "a = (v**2 - v0**2)/(2*x)",
            "x": "x = (v**2 - v0**2)/(2*a)",
        },
    ),

    # ── 4. 自由落体速度（v0=0, a=g） ──
    Formula(
        name="free_fall_velocity",
        expression="v = sqrt(2*g*h)",
        domain="kinematics",
        description="自由落体末速度（无初速度，从高度 h 落下）",
        given=["h", "g"],
        target="v",
        constraints=["h >= 0", "g > 0"],
        variants={
            "h": "h = v**2/(2*g)",
        },
    ),

    # ── 5. 自由落体时间 ──
    Formula(
        name="free_fall_time",
        expression="t = sqrt(2*h/g)",
        domain="kinematics",
        description="自由落体时间",
        given=["h", "g"],
        target="t",
        constraints=["h >= 0", "g > 0"],
    ),

    # ── 6. 抛体水平射程 ──
    Formula(
        name="projectile_range",
        expression="R = v0**2 * sin(2*theta) / g",
        domain="kinematics",
        description="抛体水平射程（发射角 theta，初速度 v0）",
        given=["v0", "theta", "g"],
        target="R",
        constraints=["g > 0", "theta >= 0", "theta <= pi/2"],
        variants={
            "v0": "v0 = sqrt(R*g / sin(2*theta))",
            "theta": "theta = asin(R*g / v0**2) / 2",
        },
    ),

    # ── 7. 抛体最大高度 ──
    Formula(
        name="projectile_max_height",
        expression="H = v0**2 * sin(theta)**2 / (2*g)",
        domain="kinematics",
        description="抛体最大高度",
        given=["v0", "theta", "g"],
        target="H",
        constraints=["g > 0"],
    ),

    # ══════════════════════════════════════════════════════
    # 二、动力学 (Dynamics) — 5 公式
    # ══════════════════════════════════════════════════════

    # ── 8. 牛顿第二定律 ──
    Formula(
        name="newton_second",
        expression="F = m*a",
        domain="dynamics",
        description="牛顿第二定律",
        given=["m", "a"],
        target="F",
        variants={
            "m": "m = F/a",
            "a": "a = F/m",
        },
    ),

    # ── 9. 重力 ──
    Formula(
        name="gravity_force",
        expression="F = m*g",
        domain="dynamics",
        description="重力",
        given=["m", "g"],
        target="F",
        variants={
            "m": "m = F/g",
        },
    ),

    # ── 10. 斜面分量 ──
    Formula(
        name="inclined_plane_parallel",
        expression="F_parallel = m*g*sin(theta)",
        domain="dynamics",
        description="斜面上重力沿斜面方向的分量",
        given=["m", "g", "theta"],
        target="F_parallel",
        constraints=["theta >= 0", "theta <= pi/2"],
    ),

    # ── 11. 斜面加速度（无摩擦） ──
    Formula(
        name="inclined_plane_accel_no_friction",
        expression="a = g*sin(theta)",
        domain="dynamics",
        description="无摩擦斜面上的加速度",
        given=["g", "theta"],
        target="a",
        constraints=["theta >= 0", "theta <= pi/2"],
    ),

    # ── 12. 斜面加速度（有摩擦） ──
    Formula(
        name="inclined_plane_accel_with_friction",
        expression="a = g*(sin(theta) - mu*cos(theta))",
        domain="dynamics",
        description="有摩擦斜面上的加速度",
        given=["g", "theta", "mu"],
        target="a",
        constraints=["sin(theta) - mu*cos(theta) > 0"],
    ),

    # ══════════════════════════════════════════════════════
    # 三、能量 (Energy) — 3 公式
    # ══════════════════════════════════════════════════════

    # ── 13. 动能 ──
    Formula(
        name="kinetic_energy",
        expression="E_k = 0.5*m*v**2",
        domain="energy",
        description="动能",
        given=["m", "v"],
        target="E_k",
        variants={
            "v": "v = sqrt(2*E_k/m)",
            "m": "m = 2*E_k/v**2",
        },
    ),

    # ── 14. 重力势能 ──
    Formula(
        name="gravitational_potential_energy",
        expression="E_p = m*g*h",
        domain="energy",
        description="重力势能",
        given=["m", "g", "h"],
        target="E_p",
        variants={
            "h": "h = E_p/(m*g)",
        },
    ),

    # ── 15. 机械能守恒 ──
    Formula(
        name="mechanical_energy_conservation",
        expression="0.5*m*v1**2 + m*g*h1 = 0.5*m*v2**2 + m*g*h2",
        domain="energy",
        description="机械能守恒（无摩擦/无外力做功）",
        given=["m", "v1", "h1", "h2", "g"],
        target="v2",
        variants={
            "v2": "v2 = sqrt(v1**2 + 2*g*(h1 - h2))",
            "h2": "h2 = h1 + (v1**2 - v2**2)/(2*g)",
        },
    ),

    # ══════════════════════════════════════════════════════
    # 四、动量 (Momentum) — 3 公式
    # ══════════════════════════════════════════════════════

    # ── 16. 动量 ──
    Formula(
        name="momentum",
        expression="p = m*v",
        domain="momentum",
        description="动量",
        given=["m", "v"],
        target="p",
        variants={
            "v": "v = p/m",
        },
    ),

    # ── 17. 动量守恒（弹性碰撞） ──
    Formula(
        name="momentum_conservation",
        expression="m1*v1_before + m2*v2_before = m1*v1_after + m2*v2_after",
        domain="momentum",
        description="动量守恒定律（需要 v2_after 才能解 v1_after）",
        given=["m1", "m2", "v1_before", "v2_before", "v2_after"],
        target="v1_after",
        variants={
            "v1_after": "v1_after = (m1*v1_before + m2*v2_before - m2*v2_after)/m1",
            "v2_after": "v2_after = (m1*v1_before + m2*v2_before - m1*v1_after)/m2",
        },
    ),

    # ── 18. 完全弹性碰撞末速度 ──
    Formula(
        name="elastic_collision_1d",
        expression="v1_after = ((m1 - m2)*v1_before + 2*m2*v2_before)/(m1 + m2)",
        domain="momentum",
        description="一维完全弹性碰撞后物体 1 的速度",
        given=["m1", "m2", "v1_before", "v2_before"],
        target="v1_after",
        constraints=["m1 + m2 > 0"],
    ),

    # ══════════════════════════════════════════════════════
    # 五、振动与单摆 (Oscillation) — 3 公式
    # ══════════════════════════════════════════════════════

    # ── 19. 弹簧周期 ──
    Formula(
        name="spring_period",
        expression="T = 2*pi*sqrt(m/k)",
        domain="kinematics",
        description="弹簧振子周期",
        given=["m", "k"],
        target="T",
        constraints=["m > 0", "k > 0"],
        variants={
            "k": "k = 4*pi**2*m / T**2",
            "m": "m = k*T**2 / (4*pi**2)",
        },
    ),

    # ── 20. 单摆周期（小角度近似） ──
    Formula(
        name="pendulum_period",
        expression="T = 2*pi*sqrt(L/g)",
        domain="kinematics",
        description="单摆周期（小角度近似，sinθ≈θ）",
        given=["L", "g"],
        target="T",
        constraints=["L > 0", "g > 0"],
        variants={
            "L": "L = g*T**2/(4*pi**2)",
            "g": "g = 4*pi**2*L/T**2",
        },
    ),
]


def match_formula(domain: str, given: dict, target: str) -> list[Formula]:
    """给定领域、已知量和目标变量，按兼容性评分排序候选公式。

    Args:
        domain: "kinematics" / "dynamics" / "energy" / "momentum"
        given: {"mass": 5, "height": 10, "g": 9.8}
        target: "velocity" / "time" / "force" / ...

    Returns:
        候选公式列表，按得分降序（得分 = 匹配的 given 参数数 - 缺失的参数数）
    """
    target_map = {
        # 运动学
        "velocity": "v", "final_velocity": "v", "speed": "v",
        "displacement": "x", "distance": "x",
        "time": "t",
        "acceleration": "a",
        "range": "R", "max_height": "H",
        # 动力学
        "force": "F", "parallel_force": "F_parallel",
        # 能量
        "kinetic_energy": "E_k", "potential_energy": "E_p",
        "velocity2": "v2",
        # 动量
        "momentum": "p", "v1_after": "v1_after", "v2_after": "v2_after",
        # 振动
        "period": "T",
    }
    sym_target = target_map.get(target, target)

    scored = []
    for f in MECHANICS_FORMULAS:
        if f.domain != domain and domain != "any":
            continue
        if f.target != sym_target and sym_target not in f.variants:
            continue

        given_set = set(given.keys())
        required_set = set(f.given)
        matched = len(given_set & required_set)
        missing = len(required_set - given_set)
        score = matched - missing

        if matched >= len(required_set):
            score += 100  # 全部已知量都有 → 大幅加分

        scored.append((score, f))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [f for _, f in scored]
