"""
PhysicsPlanner — 层级规划引擎 (杨立昆 Mode-2 规划)

H-JEPA §4.7 + §4: 梯度优化在动作空间 + 层级子目标分解

核心算法: CEM (Cross-Entropy Method) 在连续动作空间搜索最优力序列
  1. 初始化动作分布 N(mu, sigma)
  2. 采样 N_samples 个候选序列
  3. 世界模型模拟 → 代价评估
  4. 选 top-K 精英 → 更新分布
  5. 迭代至收敛 → 返回最优序列

层级:
  Level 2 (高层): 子目标分解 (直线插值 + 障碍规避)
  Level 1 (低层): CEM 力序列优化
  Level 0 (底层): 引擎模拟验证

纯 NumPy，零额外依赖。CPU only。
"""

import numpy as np
from copy import deepcopy


class PhysicsPlanner:
    """H-JEPA 层级规划器 — 世界模型的"行动力"

    杨立昆 §4 (Mode-2):
    "The actor can perform gradient-based optimization over action sequences
    to minimize the estimated future cost. This allows handling continuous
    action spaces efficiently."

    杨立昆 §4.7 (H-JEPA):
    "A high-level action sequence is inferred first. Each high-level action
    becomes a subgoal for the lower level."
    """

    def __init__(self, engine, cost_module=None):
        """初始化规划器

        Args:
            engine: WorldModelEngine 实例
            cost_module: CostModule 实例 (可选，自动创建)
        """
        self.engine = engine
        if cost_module is None:
            from cost_module import CostModule
            cost_module = CostModule(engine)
        self.cost = cost_module

        # CEM 参数
        self.n_iter = 5           # CEM 迭代轮数
        self.n_samples = 200      # 每轮采样数
        self.n_elite = 40         # 精英样本数
        self.action_scale = 50.0  # 初始动作标准差 (N)
        self.dt_action = 0.05     # 每个动作的持续时间 (s)
        self.min_sigma_frac = 0.05  # 最小探索噪声 (V1: 保持初始σ的5%)

        # 规划经验 (Mode-2 → Mode-1 迁移)
        self.skill_cache = {}     # {(from_hash, goal_hash): best_action_seq}

        # 规划状态锁 (V2: 防止规划期间外部查询读到临时状态)
        self._planning = False

    # ═══════════════════════════════════════════════════════════════
    # Level 1: CEM 力序列优化
    # ═══════════════════════════════════════════════════════════════

    def plan(self, goal, horizon=20, body_idx=0, bounds=None,
             n_iter=None, n_samples=None, n_elite=None,
             action_bounds=None):
        """CEM 规划: 找最小代价动作序列

        在连续动作空间 (2D力) 中搜索使 C(s) = IC + TC 最小的序列。

        Args:
            goal: dict — {'positions': [target_pos], ...}
            horizon: int — 动作序列长度
            body_idx: int — 控制哪个刚体
            bounds: dict — 空间边界
            n_iter, n_samples, n_elite: 覆盖默认 CEM 参数
            action_bounds: tuple (low, high) — 力幅值限制

        Returns:
            dict: {
                'actions': np.ndarray (horizon, 2) — 最优力序列
                'cost': float — 最小代价
                'trajectory': list of state — 最优轨迹
                'goal': dict — 目标
                'success': bool — 是否成功 (cost < inf)
            }
        """
        if n_iter is None:
            n_iter = self.n_iter
        if n_samples is None:
            n_samples = self.n_samples
        if n_elite is None:
            n_elite = self.n_elite

        # V4: 引擎未初始化时提前报错
        if len(self.engine.bodies) == 0:
            raise ValueError("plan() called with empty engine.bodies — add_body() first")

        # V5: goal 维度校验
        goal_pos = np.array(goal.get('positions', [[0,0,0]])[0], dtype=np.float64)
        if len(goal_pos) < 2:
            raise ValueError(f"goal position must be at least 2D, got {len(goal_pos)}D: {goal_pos}")

        action_dim = 2  # fx, fy

        # ── 检查技能缓存 (Mode-2 → Mode-1 迁移) ──
        cache_key = self._make_cache_key(goal, horizon, body_idx)
        if cache_key in self.skill_cache:
            cached = self.skill_cache[cache_key]
            return cached

        # ── 保存初始状态 ──
        saved_state = self._save_state()

        # V2: 锁住引擎 — 规划期间禁止外部查询
        self._planning = True

        # ── 初始化 CEM 分布 ──
        mu = np.zeros((horizon, action_dim))
        sigma = np.ones((horizon, action_dim)) * self.action_scale

        # 如果 goal 给出了大致方向，偏置初始分布
        mu = self._bias_init(mu, goal, body_idx)

        best_cost = float('inf')
        best_actions = None
        best_traj = None

        # ── CEM 主循环 ──
        for iteration in range(n_iter):
            # 采样
            samples = np.random.normal(
                mu, sigma, (n_samples, horizon, action_dim)
            )
            # 裁剪到合理范围
            if action_bounds is not None:
                lo, hi = action_bounds
                samples = np.clip(samples, lo, hi)

            costs = np.full(n_samples, float('inf'))
            trajectories = [None] * n_samples

            # 评估每个样本
            for s in range(n_samples):
                cost, traj = self._evaluate_sequence(
                    samples[s], goal, body_idx, bounds, saved_state
                )
                costs[s] = cost
                trajectories[s] = traj

            # 选精英
            valid_mask = costs < float('inf')
            if not np.any(valid_mask):
                # 所有样本都不可行 → 扩大搜索范围
                sigma *= 1.5
                continue

            valid_idx = np.where(valid_mask)[0]
            valid_costs = costs[valid_idx]
            sorted_idx = valid_idx[np.argsort(valid_costs)]
            elite_idx = sorted_idx[:min(n_elite, len(sorted_idx))]
            elite = samples[elite_idx]

            # 更新分布
            mu = elite.mean(axis=0)
            sigma = elite.std(axis=0) + 1e-6  # 防止退化为 0
            # V1: 保持最小探索噪声 — 维持 σ ≥ 5% 初始σ
            sigma = np.maximum(sigma, self.action_scale * self.min_sigma_frac)

            # 追踪最佳
            if costs[elite_idx[0]] < best_cost:
                best_cost = costs[elite_idx[0]]
                best_actions = samples[elite_idx[0]].copy()
                best_traj = trajectories[elite_idx[0]]

        # ── 恢复引擎状态 (plan 是查询，不应有副作用) ──
        self._restore_state(saved_state)

        # ── 解锁引擎 (V2) ──
        self._planning = False

        # ── 缓存结果 ──
        if best_actions is not None and best_cost < float('inf'):
            result = {
                'actions': best_actions,
                'cost': float(best_cost),
                'trajectory': best_traj,
                'goal': goal,
                'success': True
            }
            self.skill_cache[cache_key] = result
            return result

        return {
            'actions': mu,
            'cost': float('inf'),
            'trajectory': None,
            'goal': goal,
            'success': False
        }

    def _evaluate_sequence(self, actions, goal, body_idx, bounds, saved_state):
        """模拟一个动作序列，返回 (总代价, 轨迹)"""
        self._restore_state(saved_state)

        n_bodies = len(self.engine.bodies)
        state_dim = n_bodies * 6
        state = np.concatenate([b.state() for b in self.engine.bodies])
        trajectory = [state.copy()]

        total_cost = 0.0
        dt = self.dt_action

        for force in actions:
            # 施加力: 引擎期望 ff(s,t) 返回力向量 (3D),
            # 然后除以 mass 得到加速度
            force_vec = np.array([force[0], force[1], 0.0])

            # 临时添加外力
            self.engine.external_forces.append(
                lambda s, t, f=force_vec: f
            )

            try:
                result = self.engine.simulate(duration=dt)
                if 'error' in result:
                    return float('inf'), None
                state = result['states'][-1]
                trajectory.append(state.copy())

                # 更新引擎刚体状态 (simulate() 不自动更新 bodies)
                n_bodies = len(self.engine.bodies)
                for bi in range(n_bodies):
                    o = bi * 6
                    self.engine.bodies[bi].position = state[o:o+3].copy()
                    self.engine.bodies[bi].velocity = state[o+3:o+6].copy()
            except Exception:
                return float('inf'), None
            finally:
                # 移除临时外力
                self.engine.external_forces.pop()

            # 累积代价
            cost_result = self.cost.evaluate(state, goal, bounds)
            total_cost = cost_result['total']
            if total_cost >= float('inf'):
                break

        return total_cost, trajectory

    # ═══════════════════════════════════════════════════════════════
    # Level 2: 子目标分解 (H-JEPA §4.7)
    # ═══════════════════════════════════════════════════════════════

    def plan_hierarchical(self, goal, n_subgoals=3, body_idx=0,
                          bounds=None, horizon_per_subgoal=None,
                          n_iter=None, n_samples=None, n_elite=None):
        """层级规划 — 将复杂任务分解为子目标链

        Level 2: 从当前位置到目标位置直线插值 n_subgoals 个中间点
        Level 1: 对每个子目标调用 CEM plan()
        Level 0: 引擎模拟串联执行

        Args:
            goal: dict — 最终目标
            n_subgoals: int — 子目标数 (含最终目标)
            body_idx: int — 控制体索引
            bounds: dict — 空间边界
            horizon_per_subgoal: int — 每子目标的动作序列长度

        Returns:
            dict: {
                'subgoals': list of dict — 每个子目标
                'plans': list of dict — 每个子目标的 CEM 结果
                'total_cost': float,
                'combined_trajectory': list of state,
                'success': bool
            }
        """
        if horizon_per_subgoal is None:
            horizon_per_subgoal = max(10, 20 // n_subgoals)

        n_bodies = len(self.engine.bodies)
        o = body_idx * 6
        start_pos = self.engine.bodies[body_idx].position.copy()

        if 'positions' not in goal or len(goal['positions']) == 0:
            return {'subgoals': [], 'plans': [], 'total_cost': float('inf'),
                    'combined_trajectory': None, 'success': False}

        target_pos = np.array(goal['positions'][0])

        # ── 生成子目标 (直线插值) ──
        subgoals = []
        for i in range(1, n_subgoals + 1):
            alpha = i / n_subgoals
            sub_pos = start_pos + alpha * (target_pos - start_pos)
            subgoals.append({
                'positions': [sub_pos],
                'velocities': [np.zeros(3)]  # 期望在每个子目标处停下
            })

        # ── 逐个子目标规划 ──
        saved_original = self._save_state()
        plans = []
        combined_traj = []
        total_cost = 0.0
        all_success = True

        for sg_idx, sg in enumerate(subgoals):
            plan_result = self.plan(
                sg, horizon=horizon_per_subgoal, body_idx=body_idx,
                bounds=bounds, n_iter=n_iter, n_samples=n_samples, n_elite=n_elite
            )
            plans.append(plan_result)
            total_cost += plan_result['cost']

            if not plan_result['success']:
                all_success = False
                break

            if plan_result['trajectory']:
                combined_traj.extend(plan_result['trajectory'])

            # V3: 子目标连续性验证 — H-JEPA要求层级间状态兼容
            if sg_idx < len(subgoals) - 1 and plan_result['trajectory']:
                final_pos = plan_result['trajectory'][-1][:3]
                next_start = self.engine.bodies[body_idx].position
                gap = np.linalg.norm(final_pos - next_start)
                if gap > 0.5:  # 超过0.5m视为不连续
                    import warnings
                    warnings.warn(f"Subgoal {sg_idx}→{sg_idx+1} gap={gap:.2f}m > 0.5m — H-JEPA compatibility warning")

        self._restore_state(saved_original)

        return {
            'subgoals': subgoals,
            'plans': plans,
            'total_cost': float(total_cost),
            'combined_trajectory': combined_traj if all_success else None,
            'success': all_success
        }

    # ═══════════════════════════════════════════════════════════════
    # 辅助方法
    # ═══════════════════════════════════════════════════════════════

    def _save_state(self):
        """保存引擎完整状态"""
        return {
            'bodies': [b.copy() for b in self.engine.bodies],
            'constraints': list(self.engine.constraints),
            'collision_pairs': deepcopy(self.engine.collision_pairs),
            'joints': deepcopy(self.engine.joints),
            'external_forces': list(self.engine.external_forces),
            'gravity': self.engine.gravity.copy(),
            'dt': self.engine.dt,
        }

    def _restore_state(self, saved):
        """恢复引擎完整状态"""
        self.engine.bodies = [b.copy() for b in saved['bodies']]
        self.engine.constraints = list(saved['constraints'])
        self.engine.collision_pairs = deepcopy(saved['collision_pairs'])
        self.engine.joints = deepcopy(saved['joints'])
        self.engine.external_forces = list(saved['external_forces'])
        self.engine.gravity = saved['gravity'].copy()
        self.engine.dt = saved['dt']
        self.engine._cache = []
        self.engine.memory.clear()
        if self.engine.cost_module is not None:
            self.engine.cost_module.reset()

    def _make_cache_key(self, goal, horizon, body_idx):
        """生成技能缓存键"""
        goal_pos = goal.get('positions', [[0,0,0]])[0] if goal.get('positions') else [0,0,0]
        state_hash = tuple(round(x, 2) for x in self.engine.bodies[body_idx].position)
        goal_hash = tuple(round(x, 2) for x in goal_pos)
        return (state_hash, goal_hash, horizon, body_idx)

    def _bias_init(self, mu, goal, body_idx):
        """用目标方向偏置初始动作分布"""
        if 'positions' not in goal or not goal['positions']:
            return mu

        target = np.array(goal['positions'][0])
        current = self.engine.bodies[body_idx].position
        direction = target[:2] - current[:2]
        dist = np.linalg.norm(direction)
        if dist > 1e-6:
            direction /= dist
            # 前一半动作: 加速向目标; 后一半: 减速
            half = max(1, len(mu) // 2)
            push_force = min(self.action_scale * 0.8, dist * 2)
            mu[:half, :2] = direction * push_force
            mu[half:, :2] = -direction * push_force * 0.3

        return mu

    def clear_cache(self):
        """清空技能缓存"""
        self.skill_cache = {}
