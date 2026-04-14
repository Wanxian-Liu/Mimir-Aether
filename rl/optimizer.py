"""
PPOOptimizer - 简化版PPO优化器

使用简化版的PPO (Proximal Policy Optimization) 算法进行策略更新。

核心实现：
- PPO-clip 策略更新
- 价值网络更新
- 熵正则化
- 经验回放缓冲区

注意：这是一个概念实现，用于MimirAether的行为模式优化。
实际生产级RL需要与外部训练框架（如Tinker-Atropos, trl, OpenRLHF）集成。

Usage:
    optimizer = PPOOptimizer(model_dim=4096)
    optimizer.update(trajectories, old_log_probs, advantages)
"""

import json
import logging
import math
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
import uuid

from .collector import Trajectory, TrajectoryStep

logger = logging.getLogger(__name__)


@dataclass
class PPOConfig:
    """
    PPO配置

    Attributes:
        clip_epsilon: PPO-clip参数 (通常0.1-0.2)
        value_coef: 价值损失系数
        entropy_coef: 熵正则化系数
        learning_rate: 学习率
        max_grad_norm: 梯度裁剪
        num_epochs: 每次更新的epoch数
        batch_size: mini-batch大小
        gamma: 折扣因子
        lambda_: GAE参数
        model_dim: 模型隐层维度（用于价值网络）
        value_loss_clip: 价值损失裁剪范围
    """
    clip_epsilon: float = 0.2
    value_coef: float = 0.5
    entropy_coef: float = 0.01
    learning_rate: float = 1e-4
    max_grad_norm: float = 0.5
    num_epochs: int = 4
    batch_size: int = 8
    gamma: float = 0.99
    lambda_: float = 0.95
    model_dim: int = 4096
    value_loss_clip: float = 0.5

    def to_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in self.__dict__.items()}


class RolloutBuffer:
    """
    经验回放缓冲区

    存储轨迹数据用于PPO更新
    """

    def __init__(self):
        self.states: List[List[Dict]] = []
        self.actions: List[str] = []
        self.log_probs_old: List[float] = []
        self.rewards: List[float] = []
        self.advantages: List[float] = []
        self.returns: List[float] = []
        self.values_old: List[float] = []
        self.dones: List[bool] = []

    def add(
        self,
        state: List[Dict],
        action: str,
        log_prob: float,
        reward: float,
        value_old: float,
        done: bool,
    ):
        self.states.append(state)
        self.actions.append(action)
        self.log_probs_old.append(log_prob)
        self.rewards.append(reward)
        self.values_old.append(value_old)
        self.dones.append(done)

    def get_batches(
        self, batch_size: int
    ) -> List[Tuple[List, List, List, List, List, List]]:
        """生成mini-batch迭代器"""
        n = len(self.states)
        indices = list(range(n))

        # 随机打乱
        import random
        random.shuffle(indices)

        batches = []
        for i in range(0, n, batch_size):
            batch_indices = indices[i : i + batch_size]
            batch = (
                [self.states[j] for j in batch_indices],
                [self.actions[j] for j in batch_indices],
                [self.log_probs_old[j] for j in batch_indices],
                [self.advantages[j] for j in batch_indices],
                [self.returns[j] for j in batch_indices],
                [self.values_old[j] for j in batch_indices],
            )
            batches.append(batch)

        return batches

    def clear(self):
        self.states = []
        self.actions = []
        self.log_probs_old = []
        self.rewards = []
        self.advantages = []
        self.returns = []
        self.values_old = []
        self.dones = []

    def __len__(self) -> int:
        return len(self.states)


class PPOOptimizer:
    """
    简化版PPO优化器

    实现概念性的PPO更新逻辑。
    实际使用时需要接入真实的模型权重更新。

    PPO更新公式：
    L^CLIP(θ) = E[ min( r_t(θ) * A_t, clip(r_t(θ), 1-ε, 1+ε) * A_t ) ]

    其中 r_t(θ) = π_θ(a_t|s_t) / π_θ_old(a_t|s_t)

    Attributes:
        config: PPO配置
        buffer: 经验回放缓冲区
        step_count: 累计更新步数
    """

    def __init__(self, config: Optional[PPOConfig] = None):
        """
        Args:
            config: PPO配置
        """
        self.config = config or PPOConfig()
        self.buffer = RolloutBuffer()
        self.step_count = 0
        self._training_stats: Dict[str, List[float]] = {
            "policy_loss": [],
            "value_loss": [],
            "entropy": [],
            "total_loss": [],
        }

        logger.info(f"PPOOptimizer initialized with config: {self.config.to_dict()}")

    def compute_advantages(self, rewards: List[float], values: List[float], dones: List[bool]) -> List[float]:
        """
        计算GAE (Generalized Advantage Estimation)

        A_t = Σ_{l=0}^{T-t} (γλ)^l * δ_{t+l}
        δ_t = r_t + γ*V(s_{t+1}) - V(s_t)

        Args:
            rewards: 奖励列表
            values: 价值估计列表
            dones: 完成标志列表

        Returns:
            优势估计列表
        """
        gamma = self.config.gamma
        lambda_ = self.config.lambda_
        n = len(rewards)

        advantages = [0.0] * n
        last_gae = 0.0

        # 反向计算
        for t in reversed(range(n)):
            if t == n - 1:
                next_value = 0.0  # 终止状态价值为0
            else:
                next_value = values[t + 1]

            delta = rewards[t] + gamma * next_value * (1 - dones[t]) - values[t]
            last_gae = delta + gamma * lambda_ * (1 - dones[t]) * last_gae
            advantages[t] = last_gae

        return advantages

    def compute_returns(self, rewards: List[float], dones: List[bool]) -> List[float]:
        """
        计算折扣回报

        G_t = r_t + γ*r_{t+1} + γ^2*r_{t+2} + ...

        Args:
            rewards: 奖励列表
            dones: 完成标志列表

        Returns:
            回报列表
        """
        gamma = self.config.gamma
        n = len(rewards)
        returns = [0.0] * n
        last_return = 0.0

        for t in reversed(range(n)):
            last_return = rewards[t] + gamma * last_return * (1 - dones[t])
            returns[t] = last_return

        return returns

    def ppo_loss(
        self,
        log_probs_new: List[float],
        log_probs_old: List[float],
        advantages: List[float],
        values_new: List[float],
        values_old: List[float],
        returns: List[float],
        entropies: List[float],
    ) -> Tuple[float, float, float, float]:
        """
        计算PPO损失

        L = L^CLIP + c1 * L^VF + c2 * S[π]

        Args:
            log_probs_new: 新策略的log概率
            log_probs_old: 旧策略的log概率
            advantages: 优势估计
            values_new: 新价值估计
            values_old: 旧价值估计
            returns: 回报
            entropies: 策略熵

        Returns:
            (total_loss, policy_loss, value_loss, entropy_loss)
        """
        clip_eps = self.config.clip_epsilon
        value_coef = self.config.value_coef
        entropy_coef = self.config.entropy_coef

        # 比率 r_t = exp(log π_new - log π_old)
        ratios = [math.exp(lp_new - lp_old) for lp_new, lp_old in zip(log_probs_new, log_probs_old)]

        # Clip的策略损失
        policy_loss = 0.0
        for r, adv in zip(ratios, advantages):
            # min(r * A, clip(r, 1-ε, 1+ε) * A)
            clipped = max(min(r, 1 + clip_eps), 1 - clip_eps)
            policy_loss += min(r * adv, clipped * adv)

        policy_loss = -policy_loss / len(ratios)  # 负号：梯度上升

        # 价值损失（带裁剪）
        value_loss = 0.0
        for v_new, v_old, ret, adv in zip(values_new, values_old, returns, advantages):
            # 裁剪后的价值目标
            v_target = adv + v_old  # = returns - values_old + values_old = returns
            v_clip = v_old + max(
                min(v_new - v_old, clip_eps * abs(v_old)),
                -clip_eps * abs(v_old),
            )
            # 取裁剪和非裁剪中较大的（标准PPO实现）
            value_loss += max((v_new - v_target) ** 2, (v_clip - v_target) ** 2)

        value_loss = value_coef * value_loss / len(values_new)

        # 熵损失（负熵，鼓励探索）
        entropy_loss = -entropy_coef * sum(entropies) / len(entropies) if entropies else 0.0

        # 总损失
        total_loss = policy_loss + value_loss + entropy_loss

        return total_loss, policy_loss, value_loss, entropy_loss

    def update(
        self,
        trajectories: List[Trajectory],
        old_log_probs: Optional[List[List[float]]] = None,
        advantages: Optional[List[List[float]]] = None,
    ) -> Dict[str, float]:
        """
        执行PPO更新

        这是主更新函数，将轨迹数据转换为训练批次。

        Args:
            trajectories: 轨迹列表
            old_log_probs: 每个轨迹每步的旧log概率（可选）
            advantages: 每个轨迹每步的优势（可选）

        Returns:
            训练统计信息
        """
        if not trajectories:
            return {"policy_loss": 0.0, "value_loss": 0.0, "entropy": 0.0, "total_loss": 0.0}

        # 填充buffer
        self._fill_buffer(trajectories)

        # 计算优势和回报
        if advantages is None:
            advantages = self.compute_advantages(
                self.buffer.rewards,
                self.buffer.values_old,
                self.buffer.dones,
            )
        returns = self.compute_returns(self.buffer.rewards, self.buffer.dones)

        # 更新buffer中的优势
        self.buffer.advantages = advantages
        self.buffer.returns = returns

        # 执行多个epoch的更新
        all_losses = []
        policy_losses = []
        value_losses = []
        entropy_losses = []

        batches = self.buffer.get_batches(self.config.batch_size)

        for epoch in range(self.config.num_epochs):
            for batch in batches:
                (
                    states,
                    actions,
                    log_probs_old,
                    batch_advantages,
                    batch_returns,
                    values_old,
                ) = batch

                # 这里应该调用模型进行前向传播
                # 由于是简化版，我们使用模拟值
                # 实际实现需要接入真实模型

                # 模拟新的log概率（实际应用中从模型得到）
                import random
                log_probs_new = [lp + random.uniform(-0.1, 0.1) for lp in log_probs_old]
                values_new = [v + random.uniform(-0.1, 0.1) for v in values_old]
                entropies = [0.5] * len(actions)  # 模拟熵

                total_loss, pol_loss, val_loss, ent_loss = self.ppo_loss(
                    log_probs_new,
                    log_probs_old,
                    batch_advantages,
                    values_new,
                    values_old,
                    batch_returns,
                    entropies,
                )

                all_losses.append(total_loss)
                policy_losses.append(pol_loss)
                value_losses.append(val_loss)
                entropy_losses.append(ent_loss)

        # 统计
        avg_loss = sum(all_losses) / len(all_losses) if all_losses else 0.0
        avg_pol = sum(policy_losses) / len(policy_losses) if policy_losses else 0.0
        avg_val = sum(value_losses) / len(value_losses) if value_losses else 0.0
        avg_ent = sum(entropy_losses) / len(entropy_losses) if entropy_losses else 0.0

        stats = {
            "policy_loss": float(avg_pol),
            "value_loss": float(avg_val),
            "entropy": float(avg_ent),
            "total_loss": float(avg_loss),
            "step_count": self.step_count,
            "buffer_size": len(self.buffer),
        }

        self._training_stats["policy_loss"].append(float(avg_pol))
        self._training_stats["value_loss"].append(float(avg_val))
        self._training_stats["entropy"].append(float(avg_ent))
        self._training_stats["total_loss"].append(float(avg_loss))

        self.step_count += 1
        self.buffer.clear()

        logger.info(f"PPO update step {self.step_count}: loss={avg_loss:.4f}, policy={avg_pol:.4f}")
        return stats

    def _fill_buffer(self, trajectories: List[Trajectory]):
        """将轨迹数据填充到buffer"""
        for traj in trajectories:
            for step in traj.steps:
                state = step.messages
                action = f"{step.action_type}:{step.action_content[:50]}"
                # 模拟的旧log prob和value
                log_prob_old = step.advantage if step.advantage is not None else 0.0
                value_old = step.value_estimate if step.value_estimate is not None else 0.0
                reward = step.reward if step.reward is not None else 0.0
                done = step.action_type in ("finish", "stop")

                self.buffer.add(state, action, log_prob_old, reward, value_old, done)

    def get_training_history(self) -> Dict[str, List[float]]:
        """获取训练历史"""
        return dict(self._training_stats)

    def save(self, path: str):
        """保存优化器状态"""
        state = {
            "config": self.config.to_dict(),
            "step_count": self.step_count,
            "training_stats": self._training_stats,
            "timestamp": datetime.now().isoformat(),
        }
        with open(path, "w") as f:
            json.dump(state, f, indent=2)
        logger.info(f"Saved PPOOptimizer state to {path}")

    def load(self, path: str):
        """加载优化器状态"""
        with open(path, "r") as f:
            state = json.load(f)
        self.config = PPOConfig(**state["config"])
        self.step_count = state["step_count"]
        self._training_stats = state["training_stats"]
        logger.info(f"Loaded PPOOptimizer state from {path}")
