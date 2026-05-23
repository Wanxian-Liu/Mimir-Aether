"""
World Model Engine — 微型物理世界模型 (纯 NumPy，零额外依赖)
基于杨立昆 JEPA 理念：状态演化 + 可交互，不预测像素

核心: RK4/Verlet/Leapfrog4 数值积分 + 外力/约束 + 多体PBD碰撞 + 轨迹输出
"""
import numpy as np
from copy import deepcopy


class RigidBody:
    """刚体状态: [x, y, z, vx, vy, vz] (6维)"""
    def __init__(self, mass=1.0, position=None, velocity=None, metadata=None):
        self.mass = mass
        self.position = np.array(position, dtype=float).copy() if position is not None else np.zeros(3, dtype=float)
        self.velocity = np.array(velocity, dtype=float).copy() if velocity is not None else np.zeros(3, dtype=float)
        self.metadata = metadata or {}

    def state(self):
        return np.concatenate([self.position, self.velocity])

    def copy(self):
        return RigidBody(
            mass=self.mass,
            position=self.position.copy(),
            velocity=self.velocity.copy(),
            metadata=deepcopy(self.metadata)
        )


class MemoryBuffer:
    """JEPA 短期记忆 — (t, s, E) 三元组环形缓冲区

    杨立昆 §4.7 (H-JEPA):
    "Short-term memory stores (time, state, action, value) triplets
    for temporal credit assignment and subgoal decomposition."

    容量固定，超出时自动淘汰最旧条目。
    """
    def __init__(self, capacity=10000):
        self.capacity = capacity
        self.data = []  # [(t, state, energy), ...]

    def push(self, t, state, energy):
        """记录一个时间帧"""
        self.data.append((float(t), state.copy(), float(energy)))
        if len(self.data) > self.capacity:
            self.data.pop(0)

    def get_energy_timeseries(self):
        """返回 (时间, 能量) 序列"""
        return np.array([(t, e) for t, _, e in self.data])

    def get_state_window(self, n=100):
        """返回最近 n 个状态帧，用于子目标回溯"""
        return [(t, s) for t, s, _ in self.data[-n:]]

    def clear(self):
        self.data = []

    def __len__(self):
        return len(self.data)


class WorldModelEngine:
    """微型物理世界模型 — 杨立昆路线B核心

    RK4/Verlet/Leapfrog4 + 多体PBD约束求解 + 可交互

    零额外依赖: 纯 NumPy
    CPU only — N体状态向量 x 10000步 = 毫秒级
    """

    def __init__(self, dt=0.001, method='RK4'):
        self.dt = dt
        self.base_dt = dt       # 自适应步长基准
        self.method = method
        self.bodies = []
        self.gravity = np.array([0., -9.8, 0.])
        self.constraints = []
        self.external_forces = []
        self.events = []
        self._cache = []
        # 颗粒2: PBD约束
        self.collision_pairs = []   # [{idx1, idx2, r1, r2, restitution}]
        self.joints = []            # [{idx1, idx2, anchor1, anchor2, stiffness}]
        self.pbd_iterations = 5
        # 颗粒3: 代价函数 — 世界模型的"判断力"
        self.cost_module = None  # 延迟导入, 避免循环依赖
        # 颗粒4: 短期记忆 + 自适应步长
        self.memory = MemoryBuffer()
        self.dt_min = dt / 16    # 自适应下限
        self.dt_max = dt * 16    # 自适应上限
        self.energy_threshold = 0.05  # |dE/E| > 5% → 缩步长

    # ── 单体兼容 ──
    def add_body(self, body):
        self.bodies.append(body)

    def add_force(self, force_fn):
        self.external_forces.append(force_fn)
        return force_fn

    def add_constraint(self, constraint_fn):
        self.constraints.append(constraint_fn)
        return constraint_fn

    def add_ground(self, y=0.0, restitution=0.0):
        def ground_constraint(state):
            s = state.copy()
            n_bodies = len(self.bodies)
            for i in range(n_bodies):
                o = i * 6
                if s[o + 1] < y:
                    s[o + 1] = y
                    if s[o + 4] < 0:
                        s[o + 4] = -s[o + 4] * restitution
            return s
        return self.add_constraint(ground_constraint)

    def add_spring(self, anchor_pos, k=100.0, natural_length=1.0):
        anchor = np.array(anchor_pos, dtype=float)
        def spring_force(state, t):
            pos = state[:3]
            r = pos - anchor
            dist = np.linalg.norm(r)
            if dist < 1e-10:
                return np.zeros(3)
            return -k * (dist - natural_length) * (r / dist)
        return self.add_force(spring_force)

    def add_drag(self, coefficient=0.1):
        def drag_force(state, t):
            return -coefficient * state[3:6]
        return self.add_force(drag_force)

    # ── 颗粒2: PBD 碰撞对与关节 ──
    def add_collision_pair(self, idx1, idx2, radius1=1.0, radius2=1.0, restitution=0.5):
        """添加碰撞对 — AABB粗筛 + 精确球距 + 冲量响应"""
        self.collision_pairs.append({
            'idx1': idx1, 'idx2': idx2,
            'r1': radius1, 'r2': radius2,
            'restitution': restitution
        })

    def add_joint(self, idx1, idx2, anchor1=None, anchor2=None, stiffness=1.0):
        """添加距离关节约束 — 保持两体锚点间距恒定

        rest_length 自动从当前体位置+锚点计算，无需手动指定。
        """
        a1 = np.array(anchor1, dtype=float) if anchor1 is not None else np.zeros(3)
        a2 = np.array(anchor2, dtype=float) if anchor2 is not None else np.zeros(3)
        # 从当前状态计算初始距离
        if idx1 < len(self.bodies) and idx2 < len(self.bodies):
            world_a1 = self.bodies[idx1].position + a1
            world_a2 = self.bodies[idx2].position + a2
            rest_length = np.linalg.norm(world_a1 - world_a2)
        else:
            rest_length = 1.0
        self.joints.append({
            'idx1': idx1, 'idx2': idx2,
            'anchor1': a1, 'anchor2': a2,
            'stiffness': stiffness,
            'rest_length': rest_length
        })

    def _solve_pbd(self, state):
        """PBD迭代求解 — 碰撞+关节约束

        每积分步后调用，迭代修正穿透/拉伸。
        先碰撞后关节，先位置后速度。
        """
        n_bodies = len(self.bodies)
        if n_bodies < 2:
            return state

        s = state.copy()
        masses = np.array([b.mass for b in self.bodies])
        inv_mass = 1.0 / masses

        for _ in range(self.pbd_iterations):
            # ── 碰撞解析 (Sequential Impulse) ──
            for cp in self.collision_pairs:
                i, j = cp['idx1'], cp['idx2']
                oi, oj = i * 6, j * 6
                pi, pj = s[oi:oi+3].copy(), s[oj:oj+3].copy()
                r_vec = pi - pj
                dist = np.linalg.norm(r_vec)
                min_dist = cp['r1'] + cp['r2']

                if dist < min_dist and dist > 1e-12:
                    n = r_vec / dist
                    penetration = min_dist - dist

                    # 位置修正 (质量加权)
                    wi = inv_mass[i] / (inv_mass[i] + inv_mass[j])
                    wj = inv_mass[j] / (inv_mass[i] + inv_mass[j])
                    s[oi:oi+3] += wi * penetration * n
                    s[oj:oj+3] -= wj * penetration * n

                    # 速度修正 (恢复系数)
                    vi, vj = s[oi+3:oi+6], s[oj+3:oj+6]
                    v_rel = vi - vj
                    vn = np.dot(v_rel, n)
                    if vn < 0:  # 接近中
                        e = cp['restitution']
                        j_imp = -(1 + e) * vn / (inv_mass[i] + inv_mass[j])
                        s[oi+3:oi+6] += j_imp * n * inv_mass[i]
                        s[oj+3:oj+6] -= j_imp * n * inv_mass[j]

            # ── 关节解析 (距离约束: C = |p1+a1 - p2-a2| - rest_length) ──
            for jt in self.joints:
                i, j = jt['idx1'], jt['idx2']
                oi, oj = i * 6, j * 6
                # 世界空间锚点
                a1 = s[oi:oi+3] + jt['anchor1']
                a2 = s[oj:oj+3] + jt['anchor2']
                delta = a1 - a2
                dist = np.linalg.norm(delta)
                if dist > 1e-12:
                    n = delta / dist
                    C = dist - jt['rest_length']  # 约束违反量
                    k = jt['stiffness']
                    wi = inv_mass[i] / (inv_mass[i] + inv_mass[j])
                    wj = inv_mass[j] / (inv_mass[i] + inv_mass[j])
                    correction = k * C
                    s[oi:oi+3] -= wi * correction * n
                    s[oj:oj+3] += wj * correction * n

        return s

    # ── 多体动力学 (向后兼容单体) ──
    def _compute_acceleration(self, state, t):
        """多体加速度: 重力 + Σ外力, 返回 (n_bodies, 3)

        静态体 (mass > 1e8 或 metadata['static']) 不受力。
        """
        n_bodies = len(self.bodies)
        acc = np.zeros((n_bodies, 3))
        for i in range(n_bodies):
            body = self.bodies[i]
            is_static = body.mass > 1e8 or body.metadata.get('static', False)
            if not is_static:
                acc[i] = self.gravity.copy()

        # 外力只作用于单体场景 (向后兼容)
        if n_bodies == 1:
            for ff in self.external_forces:
                acc[0] += ff(state, t) / self.bodies[0].mass
        return acc

    def _ode_rhs(self, state, t):
        """dy/dt for n_body * 6 state vector"""
        n_bodies = len(self.bodies)
        dydt = np.zeros(n_bodies * 6)
        acc = self._compute_acceleration(state, t)
        for i in range(n_bodies):
            o = i * 6
            dydt[o:o+3] = state[o+3:o+6]   # dx/dt = v
            dydt[o+3:o+6] = acc[i]          # dv/dt = a
        return dydt

    def _rk4_step(self, state, t, dt):
        k1 = self._ode_rhs(state, t)
        k2 = self._ode_rhs(state + 0.5*dt*k1, t + 0.5*dt)
        k3 = self._ode_rhs(state + 0.5*dt*k2, t + 0.5*dt)
        k4 = self._ode_rhs(state + dt*k3, t + dt)
        new_state = state + (dt/6.0) * (k1 + 2*k2 + 2*k3 + k4)
        for c in self.constraints:
            new_state = c(new_state)
        new_state = self._solve_pbd(new_state)
        return new_state

    def _euler_step(self, state, t, dt):
        dydt = self._ode_rhs(state, t)
        new_state = state + dt * dydt
        for c in self.constraints:
            new_state = c(new_state)
        new_state = self._solve_pbd(new_state)
        return new_state

    def _verlet_step(self, state, t, dt):
        n_bodies = len(self.bodies)
        a_now = self._compute_acceleration(state, t)
        # 半步速度 (per body)
        new_state = state.copy()
        for i in range(n_bodies):
            o = i * 6
            new_state[o+3:o+6] = state[o+3:o+6] + 0.5 * dt * a_now[i]
            new_state[o:o+3] = state[o:o+3] + dt * new_state[o+3:o+6]
        a_new = self._compute_acceleration(new_state, t + dt)
        for i in range(n_bodies):
            o = i * 6
            new_state[o+3:o+6] = new_state[o+3:o+6] + 0.5 * dt * a_new[i]
        for c in self.constraints:
            new_state = c(new_state)
        new_state = self._solve_pbd(new_state)
        return new_state

    def _leapfrog4_step(self, state, t, dt):
        w0 = -2**(1/3) / (2 - 2**(1/3))
        w1 = 1 / (2 - 2**(1/3))
        coeffs = [w1, w0, w1]
        s = state.copy()
        t_cur = t
        for ci in coeffs:
            s = self._verlet_step(s, t_cur, ci * dt)
            t_cur += ci * dt
        return s

    def simulate(self, duration=1.0, adaptive=False):
        """核心: 多体物理世界演化

        Args:
            duration: float — 模拟时长 (秒)
            adaptive: bool — 是否启用自适应步长 (dE/dt 驱动)

        Returns dict: t, states (n_steps, n_bodies*6), events, energy_ts (可选)
        """
        if not self.bodies:
            return {'t': np.array([]), 'states': np.array([]), 'events': []}

        n_bodies = len(self.bodies)
        state_dim = n_bodies * 6
        state = np.concatenate([b.state() for b in self.bodies])
        if not adaptive:
            self.dt = self.base_dt
        dt = self.dt
        base_n_steps = int(duration / dt) + 1
        # 自适应模式: 预分配 ×4 (步长可能缩小)
        max_steps = base_n_steps * 4 if adaptive else base_n_steps
        times = np.zeros(max_steps)
        states = np.zeros((max_steps, state_dim))
        states[0] = state
        times[0] = 0.0

        if self.method == 'RK4':
            step_fn = self._rk4_step
        elif self.method == 'Verlet':
            step_fn = self._verlet_step
        elif self.method == 'Leapfrog4':
            step_fn = self._leapfrog4_step
        else:
            step_fn = self._euler_step

        # 能量追踪起始
        prev_energy = self._compute_energy(state)
        self.memory.push(0.0, state, prev_energy)

        i = 1
        t_cur = 0.0
        while t_cur < duration - 1e-12 and i < max_steps:
            effective_dt = min(dt, duration - t_cur)
            try:
                state = step_fn(state, t_cur, effective_dt)
            except Exception:
                result = {'t': times[:i], 'states': states[:i], 'events': []}
                result['energy_ts'] = self.memory.get_energy_timeseries()
                result['error'] = f'Integration failed at step {i}'
                return result
            if np.any(np.isnan(state)) or np.any(np.abs(state) > 1e15):
                result = {'t': times[:i], 'states': states[:i], 'events': []}
                result['energy_ts'] = self.memory.get_energy_timeseries()
                result['error'] = f'NaN or overflow at step {i}'
                return result

            t_cur += effective_dt
            times[i] = t_cur
            states[i] = state

            # 能量追踪 + MemoryBuffer
            energy = self._compute_energy(state)
            self.memory.push(t_cur, state, energy)

            # 自适应步长调整
            if adaptive and i % 10 == 0:
                dt = self._adaptive_dt_adjust(energy, prev_energy, dt)
            prev_energy = energy
            i += 1

        result = {'t': times[:i], 'states': states[:i], 'events': []}
        result['energy_ts'] = self.memory.get_energy_timeseries()
        return result

    def step(self, action=None, duration=0.01):
        """交互式步进 (多体)"""
        if action and 'impulse' in action:
            imp = np.array(action['impulse'])
            for body in self.bodies:
                body.velocity += imp / body.mass
        result = self.simulate(duration=duration)
        if len(result['states']) > 0:
            final = result['states'][-1]
            for i, body in enumerate(self.bodies):
                o = i * 6
                body.position = final[o:o+3].copy()
                body.velocity = final[o+3:o+6].copy()
        self._cache.append(result)
        return self.bodies

    def get_trajectory(self):
        """累积轨迹"""
        if not self._cache:
            return None
        all_t = []; all_s = []; offset = 0.0
        for c in self._cache:
            all_t.append(c['t'] + offset)
            all_s.append(c['states'])
            offset += c['t'][-1]
        return {'t': np.concatenate(all_t), 'states': np.concatenate(all_s, axis=0)}

    # ── 颗粒4: 短期记忆 + 自适应步长 ──
    def _compute_energy(self, state, include_kinetic=True, include_potential=True):
        """计算当前状态的总能量

        动能: Σ ½ m v²  (per body)
        势能: Σ m g y   (per body, 重力势能)

        Args:
            state: np.ndarray (n_bodies * 6)
            include_kinetic: bool
            include_potential: bool

        Returns:
            float: 总能量 (J)
        """
        n_bodies = len(self.bodies)
        if n_bodies == 0:
            return 0.0
        ke = 0.0
        pe = 0.0
        for i in range(n_bodies):
            o = i * 6
            body = self.bodies[i]
            is_static = body.mass > 1e8 or body.metadata.get('static', False)
            if include_kinetic and not is_static:
                v = state[o+3:o+6]
                ke += 0.5 * body.mass * np.dot(v, v)
            if include_potential and not is_static:
                y = state[o+1]
                pe += body.mass * (-self.gravity[1]) * y
        return ke + pe

    def energy_timeseries(self):
        """返回模拟过程中的能量-时间序列

        Returns:
            np.ndarray shape (n, 2): [[t, E], ...] 或空数组
        """
        return self.memory.get_energy_timeseries()

    def _adaptive_dt_adjust(self, energy, prev_energy, dt):
        """自适应步长调整 — dE/dt 驱动

        |dE/E| > energy_threshold → dt/2 (系统变化剧烈)
        |dE/E| < energy_threshold/10 → dt*2 (系统稳定)
        否则保持当前 dt

        Args:
            energy: float — 当前能量
            prev_energy: float — 上一步能量
            dt: float — 当前步长

        Returns:
            float: 调整后的步长
        """
        if abs(prev_energy) < 1e-12:
            return dt
        de_ratio = abs((energy - prev_energy) / prev_energy)
        if de_ratio > self.energy_threshold:
            return max(dt / 2, self.dt_min)
        elif de_ratio < self.energy_threshold / 10:
            return min(dt * 2, self.dt_max)
        return dt

    # ── 颗粒3: 代价函数 — 世界模型的"判断力" ──
    def _get_cost_module(self):
        """延迟导入 CostModule，避免循环依赖"""
        if self.cost_module is None:
            from cost_module import CostModule
            self.cost_module = CostModule(self)
        return self.cost_module

    def evaluate_cost(self, state, goal=None, bounds=None):
        """评估状态代价 C(s) = IC(s) + TC(s)

        杨立昆 JEPA §3.3: 代价函数是世界模型的核心判断力。
        IC (Intrinsic Cost) 是硬编码物理不变量，不可学习。
        TC (Task Cost) 是任务目标距离，可变。

        Args:
            state: np.ndarray (n_bodies * 6) — 当前状态向量
            goal: dict | None — 任务目标 {'positions': [...], ...}
            bounds: dict | None — 空间边界 {'x': (-10,10), ...}

        Returns:
            dict: {
                'total': float,         # C(s) = IC + TC
                'ic': float,            # 物理不变量代价
                'tc': float,            # 任务代价
                'breakdown': {...},     # IC 子项明细
                'physically_valid': bool
            }
        """
        cm = self._get_cost_module()
        return cm.evaluate(state, goal, bounds)

    def is_physically_valid(self, state, bounds=None):
        """快速检查状态是否物理合法 (IC < 阈值)

        Args:
            state: np.ndarray (n_bodies * 6)
            bounds: dict | None

        Returns:
            bool: True 表示物理合法
        """
        cm = self._get_cost_module()
        return cm.is_physically_valid(state, bounds)

    def reset(self):
        self.bodies = []
        self.constraints = []
        self.external_forces = []
        self.events = []
        self._cache = []
        self.collision_pairs = []
        self.joints = []
        self.memory.clear()
        self.dt = self.base_dt
        if self.cost_module is not None:
            self.cost_module.reset()
