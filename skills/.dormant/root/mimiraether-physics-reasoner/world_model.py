"""世界模型 — 时间演化引擎

杨立昆 JEPA 架构核心落地：
  不是"给参数→算答案"，而是"初始状态 → ODE数值积分 → 轨迹 → 可交互推演"

架构：
  ODESystem  ─→  WorldModel  ─→  trajectory + interact
  (微分方程)     (数值积分器)     (时间线 + 施加动作)

区别于 PhysicsSolver（静态单点求解）：
  - WorldModel 输出的是完整时间线，不是单个数值
  - 支持运行时交互（在 t 时刻突然推一把）
  - 能量/动量守恒可沿轨迹验证，不只是终点检查
"""

from dataclasses import dataclass, field
from typing import Callable, Optional
import math

import numpy as np
import sympy as sp
from scipy.integrate import solve_ivp


# ══════════════════════════════════════════════════════
# 1. 数据结构
# ══════════════════════════════════════════════════════

@dataclass
class StateSnapshot:
    """轨迹上单个时间点的状态快照"""
    t: float
    state: np.ndarray   # 原始状态向量
    labels: list[str]   # 每个分量的名称，如 ["x", "v"]

    def to_dict(self) -> dict:
        return {"t": round(self.t, 6), **dict(zip(self.labels, self.state))}


@dataclass
class Trajectory:
    """完整轨迹"""
    states: list[StateSnapshot] = field(default_factory=list)
    system_name: str = ""

    def plot_data(self) -> tuple[np.ndarray, np.ndarray, list[str]]:
        """导出 t 轴 + 状态矩阵 + 标签（供外部绘图用）"""
        t_arr = np.array([s.t for s in self.states])
        n_states = len(self.states[0].state) if self.states else 0
        y_arr = np.array([s.state for s in self.states])
        labels = self.states[0].labels if self.states else []
        return t_arr, y_arr, labels

    def summary(self) -> list[str]:
        """自然语言摘要"""
        lines = [f"系统: {self.system_name}"]
        lines.append(f"时间范围: {self.states[0].t:.3f}s → {self.states[-1].t:.3f}s")
        lines.append(f"步数: {len(self.states)}")
        initial = self.states[0].to_dict()
        final = self.states[-1].to_dict()
        lines.append(f"初始: {initial}")
        lines.append(f"最终: {final}")
        return lines


@dataclass
class ODESystem:
    """物理系统的微分方程定义

    state  = [q1, q2, ..., dq1, dq2, ...]
              ← 广义坐标 →  ← 广义速度 →
    """
    name: str
    labels: list[str]          # 状态变量名，如 ["y", "vy"]
    n_dof: int                 # 自由度（坐标数）
    derivatives: Callable[[float, np.ndarray], np.ndarray]  # f(t, state) → dstate/dt
    params: dict = field(default_factory=dict)  # {g: 9.8, m: 1.0, ...}

    @classmethod
    def free_fall(cls, g=9.8):
        """自由落体：state = [y, vy]"""
        def dy(t, y):
            return np.array([y[1], -g])
        return cls(name="free_fall", labels=["y", "vy"], n_dof=1,
                   derivatives=dy, params={"g": g})

    @classmethod
    def projectile(cls, g=9.8):
        """抛体 2D：state = [x, y, vx, vy]"""
        def dy(t, y):
            return np.array([y[2], y[3], 0.0, -g])
        return cls(name="projectile", labels=["x", "y", "vx", "vy"], n_dof=2,
                   derivatives=dy, params={"g": g})

    @classmethod
    def spring_mass(cls, m=1.0, k=100.0):
        """弹簧振子：state = [x, v]"""
        def dy(t, y):
            return np.array([y[1], -k/m * y[0]])
        return cls(name="spring_mass", labels=["x", "v"], n_dof=1,
                   derivatives=dy, params={"m": m, "k": k})

    @classmethod
    def pendulum(cls, L=1.0, g=9.8):
        """单摆（非小角度近似）：state = [theta, omega]"""
        def dy(t, y):
            return np.array([y[1], -g/L * np.sin(y[0])])
        return cls(name="pendulum", labels=["theta", "omega"], n_dof=1,
                   derivatives=dy, params={"L": L, "g": g})

    @classmethod
    def double_pendulum(cls, L1=1.0, L2=1.0, m1=1.0, m2=1.0, g=9.8):
        """双摆：state = [theta1, theta2, omega1, omega2]"""
        def dy(t, y):
            th1, th2, w1, w2 = y
            delta = th2 - th1
            denom1 = (m1 + m2) * L1 - m2 * L1 * np.cos(delta)**2
            denom2 = (m1 + m2) * L2 - m2 * L2 * np.cos(delta)**2
            if abs(denom1) < 1e-12 or abs(denom2) < 1e-12:
                return np.array([w1, w2, 0.0, 0.0])
            dw1 = (m2 * g * np.sin(th2) * np.cos(delta)
                   - m2 * np.sin(delta) * (L1 * w1**2 * np.cos(delta) + L2 * w2**2)
                   - (m1 + m2) * g * np.sin(th1)) / denom1
            dw2 = ((m1 + m2) * (g * np.sin(th1) * np.cos(delta)
                   - L1 * w1**2 * np.sin(delta)
                   - g * np.sin(th2))
                   + m2 * L2 * w2**2 * np.sin(delta) * np.cos(delta)) / denom2
            return np.array([w1, w2, dw1, dw2])
        return cls(name="double_pendulum", labels=["theta1", "theta2", "omega1", "omega2"],
                   n_dof=2, derivatives=dy, params={"L1": L1, "L2": L2, "m1": m1, "m2": m2, "g": g})


# ══════════════════════════════════════════════════════
# 2. WorldModel — 时间演化引擎
# ══════════════════════════════════════════════════════

@dataclass
class Interaction:
    """用户在 t 时刻施加的动作"""
    t: float
    impulse: np.ndarray     # 冲量向量，施加到速度分量
    description: str = ""
    # 注意：广义速度在 state 的后 n_dof 个分量


class WorldModel:
    """杨立昆世界模型核心 — 给定初始状态 + ODE 系统 → 预测时间演化

    使用 scipy.integrate.solve_ivp 做数值积分（RK45 自适应步长）。

    用法：
        wm = WorldModel(system=ODESystem.free_fall(g=9.8))
        traj = wm.run(state0=[10.0, 0.0], t_span=(0, 3.0))
        traj.summary()
    """

    def __init__(self, system: ODESystem):
        self.system = system

    def run(self, state0: list[float], t_span: tuple[float, float],
            dt_max: float = 0.01,
            interactions: list[Interaction] = None) -> Trajectory:
        """运行时间演化。

        Args:
            state0: 初始状态向量 [q1, ..., dq1, ...]
            t_span: (t_start, t_end)
            dt_max: 最大输出步长（密集采样用于交互注入）
            interactions: 在指定时间施加的动作列表

        Returns:
            Trajectory 含全部状态快照
        """
        state0_arr = np.array(state0, dtype=float)
        n_total = len(state0_arr)
        n_dof = self.system.n_dof

        if n_total != 2 * n_dof:
            raise ValueError(
                f"状态向量长度 {n_total} ≠ 2×自由度 {n_dof}（{2*n_dof}）。"
                f"标签: {self.system.labels}"
            )

        # 按时间排序 interactions
        if interactions:
            interactions = sorted(interactions, key=lambda x: x.t)

        # ── 收集轨迹 ──
        trajectory = Trajectory(system_name=self.system.name)
        t_current = t_span[0]
        current_state = state0_arr.copy()

        # 记录初始状态
        trajectory.states.append(StateSnapshot(
            t=t_current, state=current_state.copy(), labels=self.system.labels
        ))

        # ── 段式积分：每遇到 interaction 就切一段 ──
        segments = self._build_segments(t_span, interactions or [])

        for seg_start, seg_end in segments:
            if seg_start >= seg_end:
                continue

            # 数值积分这一段
            sol = solve_ivp(
                self.system.derivatives,
                (seg_start, seg_end),
                current_state,
                method="RK45",
                max_step=dt_max,
                rtol=1e-8, atol=1e-10,
            )

            # 记录轨迹点（排除起始点，避免重复）
            for i in range(1, len(sol.t)):
                trajectory.states.append(StateSnapshot(
                    t=float(sol.t[i]),
                    state=sol.y[:, i].copy(),
                    labels=self.system.labels,
                ))

            # 更新当前状态
            if len(sol.t) > 0:
                current_state = sol.y[:, -1].copy()
            t_current = seg_end

            # 如果有 interaction 在段尾，施加它
            interaction = self._interaction_at(interactions, seg_end) if interactions else None
            if interaction is not None:
                # 冲量 → 速度变化: delta_v = impulse / m (如果有质量)
                # 对于广义坐标系统，impulse 直接加到广义速度分量
                for j in range(min(len(interaction.impulse), n_dof)):
                    current_state[n_dof + j] += interaction.impulse[j]
                # 记录施加后的状态
                trajectory.states.append(StateSnapshot(
                    t=t_current,
                    state=current_state.copy(),
                    labels=self.system.labels + ["—" + interaction.description],
                ))

        return trajectory

    def _build_segments(self, t_span, interactions):
        """把时间区间按 interaction 时间点切段"""
        cuts = [t_span[0]]
        for ix in interactions:
            if t_span[0] < ix.t < t_span[1]:
                cuts.append(ix.t)
        cuts.append(t_span[1])
        return [(cuts[i], cuts[i+1]) for i in range(len(cuts)-1)]

    @staticmethod
    def _interaction_at(interactions, t):
        """检查 t 时刻是否有 interaction"""
        for ix in interactions:
            if abs(ix.t - t) < 1e-8:
                return ix
        return None

    # ── 便捷工厂方法 ──

    def run_free_fall(self, height=10.0, duration=None, g=9.8):
        """自由落体：从 height 静止释放"""
        if duration is None:
            duration = 2 * math.sqrt(2 * height / g)  # 留足时间
        wm = WorldModel(ODESystem.free_fall(g=g))
        return wm.run(state0=[height, 0.0], t_span=(0, duration))

    def run_spring(self, x0=0.1, m=1.0, k=100.0, duration=2.0):
        """弹簧振子：初始位移 x0，静止释放"""
        sys = ODESystem.spring_mass(m=m, k=k)
        wm = WorldModel(sys)
        return wm.run(state0=[x0, 0.0], t_span=(0, duration))

    def run_pendulum(self, theta0=0.5, L=1.0, duration=5.0, g=9.8):
        """单摆：初始角度 theta0（弧度），静止释放"""
        sys = ODESystem.pendulum(L=L, g=g)
        wm = WorldModel(sys)
        return wm.run(state0=[theta0, 0.0], t_span=(0, duration))


# ══════════════════════════════════════════════════════
# 3. 守恒律验证
# ══════════════════════════════════════════════════════

def check_energy_conservation(traj: Trajectory, system: ODESystem,
                               tolerance: float = 0.01) -> dict:
    """沿轨迹验证能量守恒

    对于力学系统，检查机械能 E = T + V 是否在 tolerance 内恒定。
    """
    # 目前支持的系统类型
    energy_series = []

    for snap in traj.states:
        if system.name == "spring_mass":
            m = system.params.get("m", 1.0)
            k = system.params.get("k", 1.0)
            x, v = snap.state[0], snap.state[1]
            E = 0.5 * m * v**2 + 0.5 * k * x**2
            energy_series.append(E)

        elif system.name == "free_fall":
            m = 1.0  # 归一化
            g = system.params.get("g", 9.8)
            y, vy = snap.state[0], snap.state[1]
            E = 0.5 * m * vy**2 + m * g * y
            energy_series.append(E)

        elif system.name == "pendulum":
            g = system.params.get("g", 9.8)
            L = system.params.get("L", 1.0)
            theta, omega = snap.state[0], snap.state[1]
            Ek = 0.5 * (L * omega)**2          # 动能 (m=1)
            Ep = g * L * (1 - np.cos(theta))   # 势能
            E = Ek + Ep
            energy_series.append(E)

    if not energy_series:
        return {"conserved": False, "error": f"不支持的系统: {system.name}"}

    energy_arr = np.array(energy_series)
    E0 = energy_arr[0]
    max_drift = np.max(np.abs(energy_arr - E0))
    conserved = max_drift / max(abs(E0), 1e-12) < tolerance

    return {
        "conserved": bool(conserved),
        "initial_energy": float(E0),
        "max_drift": float(max_drift),
        "relative_drift": float(max_drift / max(abs(E0), 1e-12)),
    }
