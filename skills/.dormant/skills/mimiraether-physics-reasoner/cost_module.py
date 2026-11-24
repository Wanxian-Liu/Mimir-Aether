"""
CostModule — 世界模型的"判断力" (杨立昆 JEPA §3.3)
=====================================================

IC(s): Intrinsic Cost — 硬编码物理不变量，不可学习
  - 能量守恒违反度
  - 动量守恒违反度
  - 约束违反度 (穿透深度/关节拉伸)
  - 边界违反度

TC(s, goal): Task Cost — 状态到目标状态的加权距离

C(s) = IC(s) + TC(s)  — 物理不变量 = +∞ 障碍，非事后检查

纯 NumPy，零额外依赖。CPU only。

EV-VOE13: 继承自 agent.self_evolution.cost_framework.AbstractCostModule（统一 IC+TC 框架）
"""

import sys
import os
import numpy as np

# 跨包引用统一 Cost 框架
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))
from agent.self_evolution.cost_framework import AbstractCostModule, CostResult


class CostModule(AbstractCostModule):
    """世界模型的代价评估器

    杨立昆核心洞察：世界模型的真正能力不是"预测状态"，
    而是"判断状态好不好"。代价函数提供了这个判断力。

    IC 不可变（硬编码物理定律），TC 可变（每任务不同）。
    """

    def __init__(self, engine=None):
        """初始化代价模块

        Args:
            engine: WorldModelEngine 实例，用于获取 bodies 和约束信息
        """
        self.engine = engine
        # ── IC 权重 (可调，但物理不变量的阈值不可调) ──
        self.w_energy = 1.0        # 能量守恒违反权重
        self.w_momentum = 1.0      # 动量守恒违反权重
        self.w_constraint = 10.0   # 约束违反权重 (穿透/拉伸)
        self.w_boundary = 100.0    # 边界违反权重 (出界 → 高代价)

        # ── 障碍阈值 ──
        self.inf_threshold = 1e10  # 超过此值视为 +∞
        self._reference_energy = None  # 初始参考能量 (用于计算能量违反)

    # ═══════════════════════════════════════════════════════════════
    # IC: 物理不变量代价 (不可学习)
    # ═══════════════════════════════════════════════════════════════

    def energy_cost(self, state):
        """能量守恒违反度

        当前能量偏离初始参考能量的比例。
        对保守系统，总能量应保持不变。

        Returns:
            float: 能量违反度 ∈ [0, +∞)。0 = 完美守恒。
        """
        if self.engine is None or not self.engine.bodies:
            return 0.0

        bodies = self.engine.bodies
        g = self.engine.gravity
        n_bodies = len(bodies)
        ke = 0.0
        pe = 0.0

        for i in range(n_bodies):
            o = i * 6
            v = state[o+3:o+6]
            r = state[o:o+3]
            m = bodies[i].mass
            ke += 0.5 * m * np.dot(v, v)
            # PE = -m * g·r (以 g 方向为参考)
            pe -= m * np.dot(g, r)

        total = ke + pe

        # 首次调用设定参考能量
        if self._reference_energy is None:
            self._reference_energy = total
            return 0.0

        if abs(self._reference_energy) < 1e-10:
            return 0.0

        violation = abs(total - self._reference_energy) / abs(self._reference_energy)
        return violation

    def momentum_cost(self, state):
        """动量守恒违反度

        对外力为零的系统，总动量应保持不变。
        重力是外力，所以这里只检测"有无意外动量变化"。
        实际上检查的是: 总动量相对于初始动量的漂移。

        Returns:
            float: 动量违反度 ∈ [0, +∞)
        """
        if self.engine is None or not self.engine.bodies:
            return 0.0

        bodies = self.engine.bodies
        n_bodies = len(bodies)
        total_p = np.zeros(3)

        for i in range(n_bodies):
            o = i * 6
            total_p += bodies[i].mass * state[o+3:o+6]

        if not hasattr(self, '_reference_momentum'):
            self._reference_momentum = np.linalg.norm(total_p)
            return 0.0

        current_p = np.linalg.norm(total_p)
        # 动量变化率 (简化: 只检查幅值)
        if self._reference_momentum < 1e-10:
            return 0.0
        return abs(current_p - self._reference_momentum) / self._reference_momentum

    def constraint_cost(self, state):
        """约束违反度 — 穿透深度 + 关节拉伸

        检查所有碰撞对和关节的约束违反量。

        Returns:
            float: 约束违反度 ∈ [0, +∞)。0 = 无违反。
        """
        if self.engine is None:
            return 0.0

        cost = 0.0
        n_bodies = len(self.engine.bodies)

        # ── 碰撞穿透 ──
        for cp in self.engine.collision_pairs:
            i, j = cp['idx1'], cp['idx2']
            if i >= n_bodies or j >= n_bodies:
                continue
            oi, oj = i * 6, j * 6
            pi, pj = state[oi:oi+3], state[oj:oj+3]
            dist = np.linalg.norm(pi - pj)
            min_dist = cp['r1'] + cp['r2']
            if dist < min_dist:
                penetration = min_dist - dist
                cost += penetration ** 2  # 平方惩罚大穿透

        # ── 关节拉伸 ──
        for jt in self.engine.joints:
            i, j = jt['idx1'], jt['idx2']
            if i >= n_bodies or j >= n_bodies:
                continue
            oi, oj = i * 6, j * 6
            a1 = state[oi:oi+3] + jt['anchor1']
            a2 = state[oj:oj+3] + jt['anchor2']
            dist = np.linalg.norm(a1 - a2)
            stretch = abs(dist - jt['rest_length'])
            cost += stretch ** 2

        return cost

    def boundary_cost(self, state, bounds=None):
        """边界违反度

        检查状态是否超出物理上合理的范围。

        Args:
            bounds: dict, 如 {'x': (-100, 100), 'y': (-50, 50), 'z': (-100, 100)}
                    None 则无边界限制。

        Returns:
            float: 边界违反度。如果出界则返回 +∞。
        """
        if bounds is None:
            return 0.0

        n_bodies = len(self.engine.bodies) if self.engine else 0
        for i in range(n_bodies):
            o = i * 6
            for dim_idx, dim in enumerate(['x', 'y', 'z']):
                if dim in bounds:
                    lo, hi = bounds[dim]
                    val = state[o + dim_idx]
                    if val < lo or val > hi:
                        return float('inf')

        return 0.0

    # ═══════════════════════════════════════════════════════════════
    # IC: 组合代价
    # ═══════════════════════════════════════════════════════════════

    def ic(self, state, bounds=None):
        """Intrinsic Cost — 物理不变量总代价

        IC = Σ w_i * cost_i

        IC ≥ 0，完美物理状态 = 0。+∞ 表示物理上不可能。
        """
        e = self.w_energy * self.energy_cost(state)
        m = self.w_momentum * self.momentum_cost(state)
        c = self.w_constraint * self.constraint_cost(state)
        b = self.w_boundary * self.boundary_cost(state, bounds)

        total = e + m + c + b
        return total

    # ═══════════════════════════════════════════════════════════════
    # TC: 任务代价 (可变)
    # ═══════════════════════════════════════════════════════════════

    def tc(self, state, goal, weights=None):
        """Task Cost — 状态到目标的加权距离

        Args:
            state: np.ndarray (n_bodies * 6)
            goal: dict, 如:
                {'positions': [pos1, pos2, ...],   # 目标位置列表
                 'velocities': [vel1, vel2, ...],  # 目标速度列表 (可选)
                 'body_indices': [0, 1, ...]}       # 只计算指定体的代价 (可选)
            weights: dict, 如 {'pos': 1.0, 'vel': 0.5}

        Returns:
            float: 任务代价。越小越好。
        """
        if weights is None:
            weights = {'pos': 1.0, 'vel': 0.3}

        cost = 0.0
        indices = goal.get('body_indices',
                          list(range(len(goal.get('positions', [])))))

        # ── 位置距离 ──
        if 'positions' in goal:
            for idx, target_pos in zip(indices, goal['positions']):
                if idx * 6 + 3 <= len(state):
                    o = idx * 6
                    pos = state[o:o+3]
                    cost += weights['pos'] * np.linalg.norm(pos - np.array(target_pos))

        # ── 速度距离 ──
        if 'velocities' in goal:
            for idx, target_vel in zip(indices, goal['velocities']):
                if idx * 6 + 6 <= len(state):
                    o = idx * 6
                    vel = state[o+3:o+6]
                    cost += weights['vel'] * np.linalg.norm(vel - np.array(target_vel))

        return cost

    # ═══════════════════════════════════════════════════════════════
    # C(s) = IC(s) + TC(s)
    # ═══════════════════════════════════════════════════════════════

    def evaluate(self, state, goal=None, bounds=None):
        """总代价 C(s) = IC(s) + TC(s, goal)

        杨立昆核心公式：世界模型通过代价函数判断状态好坏。
        IC 确保物理合法性，TC 驱动向目标演化。

        Args:
            state: np.ndarray (n_bodies * 6)
            goal: dict (optional) — 任务目标
            bounds: dict (optional) — 空间边界

        Returns:
            dict: {
                'total': float,     # C(s) = IC + TC
                'ic': float,        # 物理不变量代价
                'tc': float,        # 任务代价
                'breakdown': {      # IC 子项
                    'energy': float,
                    'momentum': float,
                    'constraint': float,
                    'boundary': float
                },
                'physically_valid': bool  # IC < inf_threshold
            }
        """
        ic_val = self.ic(state, bounds)
        tc_val = self.tc(state, goal) if goal else 0.0

        # 障碍函数：IC 超过阈值 → +∞
        if ic_val >= self.inf_threshold:
            ic_val = float('inf')

        return {
            'total': ic_val + tc_val,
            'ic': ic_val,
            'tc': tc_val,
            'breakdown': {
                'energy': self.w_energy * self.energy_cost(state),
                'momentum': self.w_momentum * self.momentum_cost(state),
                'constraint': self.w_constraint * self.constraint_cost(state),
                'boundary': self.w_boundary * self.boundary_cost(state, bounds)
            },
            'physically_valid': ic_val < self.inf_threshold
        }

    def is_physically_valid(self, state, bounds=None):
        """快速检查: 状态是否物理上合法

        IC < inf_threshold → 合法。用于模拟中的实时验证。
        """
        ic_val = self.ic(state, bounds)
        return ic_val < self.inf_threshold

    # ── AbstractCostModule 抽象方法实现（EV-VOE13）──

    def _compute_ic(self, state, **kwargs) -> tuple:
        """实现 AbstractCostModule._compute_ic — 委托给现有 ic() 方法"""
        bounds = kwargs.get("bounds", None)
        cost = self.ic(state, bounds)
        violations = []
        if cost >= self.inf_threshold:
            violations.append(f"ic_cost={cost} exceeds inf_threshold")
        return (float("inf") if cost >= self.inf_threshold else cost, violations)

    def _compute_tc(self, state, goal=None, **kwargs) -> tuple:
        """实现 AbstractCostModule._compute_tc — 委托给现有 tc() 方法"""
        if goal is None:
            return (0.0, {})
        weights = kwargs.get("weights", None)
        cost = self.tc(state, goal, weights)
        return (cost, {"pos_distance": cost})

    def reset(self):
        """重置参考状态 (用于新模拟)"""
        self._reference_energy = None
        if hasattr(self, '_reference_momentum'):
            delattr(self, '_reference_momentum')
