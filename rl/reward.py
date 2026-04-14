"""
RewardCalculator - 奖励计算器

基于结果计算奖励，支持可配置的奖励函数。

核心功能：
- 基于对话结果的奖励计算
- 工具调用效率奖励
- 可配置的奖励函数
- 奖励归一化和缩放
"""

import json
import logging
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Callable, Union
from datetime import datetime

from .collector import Trajectory, TrajectoryStep

logger = logging.getLogger(__name__)


@dataclass
class RewardConfig:
    """
    奖励配置

    Attributes:
        base_success_reward: 任务成功的基础奖励
        base_failure_reward: 任务失败的惩罚
        base_partial_reward: 部分完成的奖励
        tool_call_reward: 每个工具调用的奖励
        tool_call_penalty: 无效工具调用的惩罚
        helpfulness_bonus: 回答有帮助时的奖励
        efficiency_threshold: 效率阈值（步数内完成任务的奖励）
        efficiency_bonus: 效率奖励
        max_reward_cap: 最大奖励上限
        min_reward_cap: 最小奖励下限
    """
    base_success_reward: float = 1.0
    base_failure_reward: float = -0.5
    base_partial_reward: float = 0.0
    tool_call_reward: float = 0.05
    tool_call_penalty: float = -0.1
    helpfulness_bonus: float = 0.2
    efficiency_threshold: int = 10  # 10步内完成获得效率奖励
    efficiency_bonus: float = 0.3
    max_reward_cap: float = 2.0
    min_reward_cap: float = -1.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict_safe(self)


def asdict_safe(obj) -> Dict:
    """安全转换为dict，处理 dataclass"""
    if hasattr(obj, "__dataclass_fields__"):
        return {k: asdict_safe(v) for k, v in obj.__dict__.items()}
    elif isinstance(obj, list):
        return [asdict_safe(i) for i in obj]
    elif isinstance(obj, dict):
        return {k: asdict_safe(v) for k, v in obj.items()}
    return obj


class RewardCalculator:
    """
    奖励计算器

    支持两种模式：
    1. 基于outcome的简单奖励
    2. 可配置的自定义奖励函数

    Usage:
        # 简单模式
        calc = RewardCalculator()
        calc.calculate(trajectory)

        # 自定义奖励函数
        def my_reward(trajectory: Trajectory, step: TrajectoryStep) -> float:
            if step.tool_name == "search":
                return 0.1
            return 0.0

        calc = RewardCalculator(reward_fn=my_reward)

        # 使用预定义的增强奖励
        calc = RewardCalculator(config=RewardConfig(
            base_success_reward=2.0,
            efficiency_threshold=5,
        ))
    """

    def __init__(
        self,
        config: Optional[RewardConfig] = None,
        reward_fn: Optional[Callable[[Trajectory, TrajectoryStep], float]] = None,
        normalize: bool = True,
    ):
        """
        Args:
            config: 奖励配置
            reward_fn: 自定义奖励函数 (trajectory, step) -> reward
            normalize: 是否对奖励进行归一化
        """
        self.config = config or RewardConfig()
        self.reward_fn = reward_fn
        self.normalize = normalize
        self._reward_history: List[float] = []

        logger.info(f"RewardCalculator initialized, normalize={normalize}")

    def calculate(self, trajectory: Trajectory) -> Trajectory:
        """
        计算轨迹中每步的奖励

        Args:
            trajectory: 输入轨迹

        Returns:
            带奖励的轨迹（原地修改）
        """
        # 计算每步的基础奖励
        for i, step in enumerate(trajectory.steps):
            if self.reward_fn:
                # 自定义奖励函数
                reward = self.reward_fn(trajectory, step)
            else:
                # 默认奖励逻辑
                reward = self._default_reward(trajectory, step, i)

            step.reward = reward

        # 计算最终结果的奖励
        final_reward = self._outcome_reward(trajectory)
        if trajectory.steps:
            # 追加到最后一步
            trajectory.steps[-1].reward = (
                trajectory.steps[-1].reward or 0.0
            ) + final_reward

        # 归一化（可选）
        if self.normalize:
            self._normalize_trajectory(trajectory)

        # 更新统计
        for step in trajectory.steps:
            if step.reward is not None:
                self._reward_history.append(step.reward)

        return trajectory

    def _default_reward(
        self, trajectory: Trajectory, step: TrajectoryStep, index: int
    ) -> float:
        """
        默认奖励逻辑

        策略：
        - 工具调用有小额正奖励（鼓励使用工具）
        - 文本回复有轻微正奖励
        - 工具结果作为反馈信号
        """
        reward = 0.0

        if step.action_type == "tool_call":
            reward = self.config.tool_call_reward
        elif step.action_type == "text":
            # 有实质内容的回复
            if len(step.action_content) > 50:
                reward = 0.02
        elif step.action_type == "tool_result":
            # 工具结果作为中间反馈
            if "error" in step.action_content.lower() or "failed" in step.action_content.lower():
                reward = self.config.tool_call_penalty
            else:
                reward = 0.01

        return reward

    def _outcome_reward(self, trajectory: Trajectory) -> float:
        """
        根据任务结果计算奖励

        结合步数效率进行奖励：
        - 成功且高效：额外奖励
        - 成功但冗长：正常奖励
        - 失败：惩罚
        """
        outcome = trajectory.outcome
        num_steps = len(trajectory.steps)

        if outcome == "success":
            reward = self.config.base_success_reward
            # 效率奖励
            if num_steps <= self.config.efficiency_threshold:
                reward += self.config.efficiency_bonus
        elif outcome == "failure":
            reward = self.config.base_failure_reward
        else:  # partial
            reward = self.config.base_partial_reward

        return reward

    def _normalize_trajectory(self, trajectory: Trajectory):
        """
        归一化轨迹中的奖励

        使用历史的均值和标准差进行Z-score归一化，
        然后缩放到 [-1, 1] 或 [config.min, config.max]
        """
        if len(self._reward_history) < 2:
            return

        mean = sum(self._reward_history) / len(self._reward_history)
        variance = sum((r - mean) ** 2 for r in self._reward_history) / len(self._reward_history)
        std = variance ** 0.5

        if std < 1e-6:
            return

        for step in trajectory.steps:
            if step.reward is not None:
                normalized = (step.reward - mean) / std
                # 缩放到配置的范围
                step.reward = max(
                    self.config.min_reward_cap,
                    min(self.config.max_reward_cap, normalized)
                )

    def batch_calculate(self, trajectories: List[Trajectory]) -> List[Trajectory]:
        """批量计算轨迹奖励"""
        results = []
        for t in trajectories:
            results.append(self.calculate(t))
        return results

    def get_statistics(self) -> Dict[str, Any]:
        """获取奖励统计"""
        if not self._reward_history:
            return {"count": 0}

        return {
            "count": len(self._reward_history),
            "mean": sum(self._reward_history) / len(self._reward_history),
            "min": min(self._reward_history),
            "max": max(self._reward_history),
            "recent": self._reward_history[-10:],
        }


# ============================================================================
# 预定义奖励函数
# ============================================================================

def helpfulness_reward(trajectory: Trajectory, step: TrajectoryStep) -> float:
    """
    基于帮助性的奖励函数

    奖励策略：
    - 提供有用信息：+0.1
    - 解决问题：+0.3
    - 有错误或误导：-0.2
    """
    if step.action_type == "text":
        content = step.action_content.lower()
        if any(kw in content for kw in ["here is", "here's", "the answer", "solution", "result"]):
            return 0.1
        if any(kw in content for kw in ["i'm sorry", "i apologize", "i was wrong"]):
            return -0.05
    elif step.action_type == "tool_call":
        return 0.05
    return 0.0


def efficiency_reward(trajectory: Trajectory, step: TrajectoryStep) -> float:
    """
    基于效率的奖励函数

    惩罚冗长和无意义的回复
    """
    if step.action_type == "text":
        content = step.action_content
        if len(content) < 20 and "!" not in content:
            # 简短的确认性回复
            return 0.02
        elif len(content) > 1000:
            # 过长的回复可能不高效
            return 0.01
    return 0.0


def composite_reward(config: RewardConfig):
    """
    创建复合奖励函数

    结合多种奖励策略
    """
    def reward(trajectory: Trajectory, step: TrajectoryStep) -> float:
        r = 0.0
        r += helpfulness_reward(trajectory, step)
        r += efficiency_reward(trajectory, step)
        return r

    return reward
