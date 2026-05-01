"""
TrajectoryCollector - 轨迹收集器

从Agent对话历史中提取和存储轨迹数据。
支持从原始对话消息到LLM友好的轨迹格式转换。

核心功能:
- 从 Message history 生成 Trajectory
- 支持 ToolCall 标注的动作
- 存储和检索轨迹
- 轨迹统计和导出
"""

import json
import uuid
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import List, Dict, Any, Optional, Callable, Union

logger = logging.getLogger(__name__)


@dataclass
class TrajectoryStep:
    """
    单步轨迹

    表示Agent在单个时间步的状态-动作-回报。
    """
    step_id: str                           # 唯一标识
    timestamp: str                         # ISO格式时间戳

    # 状态 (State): 当前的对话上下文
    messages: List[Dict[str, str]]        # 到此步为止的消息历史
    context_summary: str                  # 上下文摘要（用于压缩）

    # 动作 (Action): Agent采取的行动
    action_type: str                      # "text" | "tool_call" | "finish"
    action_content: str                   # 动作内容（文本或工具名）
    action_args: Optional[Dict] = None   # 工具参数（如果有）
    tool_name: Optional[str] = None       # 工具名（如果是工具调用）
    tool_call_id: Optional[str] = None    # 工具调用ID

    # 奖励 (Reward): 即时奖励（后续由RewardCalculator填充）
    reward: Optional[float] = None        # 奖励值

    # 价值估计 (Value Estimate)
    value_estimate: Optional[float] = None  # V(s) 估计

    # 优势 (Advantage)
    advantage: Optional[float] = None      # A(s,a) = Q(s,a) - V(s)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return asdict(self)


@dataclass
class Trajectory:
    """
    完整轨迹

    表示一个完整对话的轨迹数据（从用户消息到最终结果）。
    """
    trajectory_id: str                    # 唯一标识
    created_at: str                       # 创建时间
    task: str                            # 用户任务描述
    outcome: str                          # 最终结果 ("success" | "failure" | "partial")

    # 元信息
    model: str = "unknown"                # 使用的模型
    platform: str = "unknown"             # 运行平台
    session_id: str = ""                  # 会话ID

    # 轨迹步骤
    steps: List[TrajectoryStep] = field(default_factory=list)

    # 统计
    total_reward: float = 0.0             # 累计奖励
    num_tool_calls: int = 0               # 工具调用次数
    num_turns: int = 0                   # 对话轮次

    def compute_returns(self, gamma: float = 0.99, lambda_: float = 0.95):
        """
        计算每步的回报 G_t 和优势 A_t

        使用 GAE (Generalized Advantage Estimation):
        A_t = Σ_{l=0}^{T-t} (γλ)^l * δ_{t+l}
        其中 δ_t = r_t + γ*V(s_{t+1}) - V(s_t)

        Args:
            gamma: 折扣因子
            lambda_: GAE参数
        """
        if not self.steps:
            return

        n = len(self.steps)
        rewards = [s.reward if s.reward is not None else 0.0 for s in self.steps]

        # 初始化
        for s in self.steps:
            s.advantage = None

        # 计算 rewards -> returns (使用 discounts)
        # G_t = r_t + γ*r_{t+1} + γ^2*r_{t+2} + ...
        discounts = [gamma ** i for i in range(n)]
        returns = []
        for t in range(n):
            future_rewards = rewards[t:]
            g_t = sum(d * r for d, r in zip(discounts[:len(future_rewards)], future_rewards))
            returns.append(g_t)

        # 设置每步的回报
        for s, ret in zip(self.steps, returns):
            s.reward = ret  # 用回报覆盖原始奖励（原始reward字段保留在total_reward）

        self.total_reward = sum(returns)

    def to_llm_format(self) -> str:
        """
        转换为LLM友好的格式

        Returns:
            可读的轨迹文本
        """
        lines = [
            f"## Trajectory {self.trajectory_id[:8]}",
            f"Task: {self.task}",
            f"Outcome: {self.outcome}",
            f"Model: {self.model}",
            "",
        ]

        for i, step in enumerate(self.steps):
            lines.append(f"### Step {i+1}")
            lines.append(f"[State] {step.context_summary[:200]}")
            lines.append(f"[Action] {step.action_type}: {step.action_content[:100]}")
            if step.tool_name:
                lines.append(f"  Tool: {step.tool_name}")
            if step.reward is not None:
                lines.append(f"[Reward] {step.reward:.4f}")
            lines.append("")

        lines.append(f"Total Reward: {self.total_reward:.4f}")
        return "\n".join(lines)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "trajectory_id": self.trajectory_id,
            "created_at": self.created_at,
            "task": self.task,
            "outcome": self.outcome,
            "model": self.model,
            "platform": self.platform,
            "session_id": self.session_id,
            "steps": [s.to_dict() for s in self.steps],
            "total_reward": self.total_reward,
            "num_tool_calls": self.num_tool_calls,
            "num_turns": self.num_turns,
        }


class TrajectoryCollector:
    """
    轨迹收集器

    从对话历史中提取轨迹数据并管理存储。

    Usage:
        collector = TrajectoryCollector()

        # 从对话历史添加
        collector.add_from_messages(
            messages=conversation_history,
            task="用户的任务描述",
            outcome="success",
            model="deepseek-chat",
        )

        # 从单个turn添加
        collector.add_turn(
            user_message="用户消息",
            assistant_message="助手响应",
            tool_calls=[...],
            outcome="success",
        )

        # 导出
        trajectories = collector.get_all()
        collector.export_jsonl("/path/to/trajectories.jsonl")
    """

    def __init__(self, storage_dir: Optional[str] = None):
        """
        Args:
            storage_dir: 轨迹存储目录（可选）
        """
        self.storage_dir = storage_dir
        self._trajectories: List[Trajectory] = []

        if storage_dir:
            import os
            os.makedirs(storage_dir, exist_ok=True)

        logger.info(f"TrajectoryCollector initialized, storage_dir={storage_dir}")

    def add_from_messages(
        self,
        messages: List[Dict],
        task: str,
        outcome: str,
        model: str = "unknown",
        platform: str = "unknown",
        session_id: str = "",
    ) -> Trajectory:
        """
        从消息历史创建轨迹

        Args:
            messages: 消息列表，格式为 [{"role": "user"|"assistant"|"tool", "content": "...", ...}]
            task: 用户任务描述
            outcome: 结果 ("success" | "failure" | "partial")
            model: 模型名称
            platform: 平台
            session_id: 会话ID

        Returns:
            创建的 Trajectory
        """
        trajectory = Trajectory(
            trajectory_id=str(uuid.uuid4()),
            created_at=datetime.now().isoformat(),
            task=task,
            outcome=outcome,
            model=model,
            platform=platform,
            session_id=session_id,
        )

        # 构建消息历史
        history: List[Dict[str, str]] = []

        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")

            # 跳过空消息
            if not content:
                continue

            # 构建当前步骤的state
            step = TrajectoryStep(
                step_id=str(uuid.uuid4()),
                timestamp=datetime.now().isoformat(),
                messages=list(history),  # 复制
                context_summary=self._summarize_context(history),
                action_type="unknown",
                action_content="",
            )

            if role == "user":
                step.action_type = "user_message"
                step.action_content = content[:500]  # 截断
            elif role == "assistant":
                # 检查是否有工具调用
                tool_calls = msg.get("tool_calls", [])
                if tool_calls:
                    # 多个工具调用，拆成多个step
                    for tc in tool_calls:
                        tool_step = TrajectoryStep(
                            step_id=str(uuid.uuid4()),
                            timestamp=datetime.now().isoformat(),
                            messages=list(history),
                            context_summary=self._summarize_context(history),
                            action_type="tool_call",
                            action_content=tc.get("name", "unknown"),
                            tool_name=tc.get("name"),
                            tool_call_id=tc.get("id"),
                            action_args=tc.get("arguments", {}),
                        )
                        trajectory.steps.append(tool_step)
                        trajectory.num_tool_calls += 1
                        # 添加工具消息到历史
                        history.append({"role": "assistant", "content": f"[Tool: {tc.get('name')}]"})
                    continue  # 不再添加单独的assistant step
                else:
                    step.action_type = "text"
                    step.action_content = content[:500]
            elif role == "tool":
                step.action_type = "tool_result"
                step.action_content = content[:500]
                step.tool_call_id = msg.get("tool_call_id")
                # 工具结果添加到历史
                history.append({"role": "tool", "content": content[:200]})
            else:
                step.action_type = "other"
                step.action_content = content[:200]

            trajectory.steps.append(step)
            history.append({"role": role, "content": content[:200]})

        # 统计
        trajectory.num_turns = len([s for s in trajectory.steps if s.action_type in ("user_message", "text")])

        self._trajectories.append(trajectory)
        logger.info(f"Added trajectory {trajectory.trajectory_id[:8]} with {len(trajectory.steps)} steps")

        return trajectory

    def add_turn(
        self,
        user_message: str,
        assistant_message: str,
        tool_calls: Optional[List[Dict]] = None,
        outcome: str = "partial",
        model: str = "unknown",
        session_id: str = "",
    ) -> Trajectory:
        """
        从单个对话轮次创建轨迹

        简化接口：适用于单轮交互的轨迹收集。

        Args:
            user_message: 用户消息
            assistant_message: 助手消息
            tool_calls: 工具调用列表
            outcome: 结果
            model: 模型名称
            session_id: 会话ID

        Returns:
            创建的 Trajectory
        """
        messages = [
            {"role": "user", "content": user_message},
            {"role": "assistant", "content": assistant_message},
        ]
        if tool_calls:
            messages[1]["tool_calls"] = tool_calls

        return self.add_from_messages(
            messages=messages,
            task=user_message[:200],
            outcome=outcome,
            model=model,
            session_id=session_id,
        )

    def add_trajectory(self, trajectory: Trajectory):
        """直接添加已构建的Trajectory"""
        self._trajectories.append(trajectory)

    def get_all(self) -> List[Trajectory]:
        """获取所有轨迹"""
        return list(self._trajectories)

    def get_recent(self, n: int = 100) -> List[Trajectory]:
        """获取最近n条轨迹"""
        return self._trajectories[-n:]

    def get_by_outcome(self, outcome: str) -> List[Trajectory]:
        """按结果筛选轨迹"""
        return [t for t in self._trajectories if t.outcome == outcome]

    def get_statistics(self) -> Dict[str, Any]:
        """获取轨迹统计"""
        total = len(self._trajectories)
        if total == 0:
            return {"total": 0}

        outcomes = {}
        total_rewards = []
        tool_calls = 0

        for t in self._trajectories:
            outcomes[t.outcome] = outcomes.get(t.outcome, 0) + 1
            total_rewards.append(t.total_reward)
            tool_calls += t.num_tool_calls

        return {
            "total": total,
            "outcomes": outcomes,
            "avg_reward": sum(total_rewards) / len(total_rewards),
            "total_tool_calls": tool_calls,
            "avg_steps_per_trajectory": sum(len(t.steps) for t in self._trajectories) / total,
        }

    def export_jsonl(self, path: str):
        """导出为JSONL格式"""
        with open(path, "w", encoding="utf-8") as f:
            for t in self._trajectories:
                f.write(json.dumps(t.to_dict(), ensure_ascii=False) + "\n")
        logger.info(f"Exported {len(self._trajectories)} trajectories to {path}")

    def import_jsonl(self, path: str) -> int:
        """从JSONL导入轨迹"""
        count = 0
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    d = json.loads(line)
                    traj = self._dict_to_trajectory(d)
                    self._trajectories.append(traj)
                    count += 1
                except Exception as e:
                    logger.warning(f"Failed to parse trajectory line: {e}")

        logger.info(f"Imported {count} trajectories from {path}")
        return count

    def _dict_to_trajectory(self, d: Dict) -> Trajectory:
        """从字典恢复Trajectory"""
        steps = [TrajectoryStep(**s) for s in d.get("steps", [])]
        traj = Trajectory(
            trajectory_id=d["trajectory_id"],
            created_at=d["created_at"],
            task=d["task"],
            outcome=d["outcome"],
            model=d.get("model", "unknown"),
            platform=d.get("platform", "unknown"),
            session_id=d.get("session_id", ""),
            steps=steps,
            total_reward=d.get("total_reward", 0.0),
            num_tool_calls=d.get("num_tool_calls", 0),
            num_turns=d.get("num_turns", 0),
        )
        return traj

    def _summarize_context(self, messages: List[Dict[str, str]], max_chars: int = 300) -> str:
        """生成上下文摘要"""
        if not messages:
            return ""

        parts = []
        for msg in messages[-4:]:  # 最近4条
            role = msg.get("role", "?")
            content = msg.get("content", "")
            parts.append(f"{role}: {content[:100]}")

        summary = " | ".join(parts)
        if len(summary) > max_chars:
            summary = summary[:max_chars] + "..."
        return summary

    def clear(self):
        """清空所有轨迹"""
        self._trajectories = []
        logger.info("Cleared all trajectories")

    def __len__(self) -> int:
        return len(self._trajectories)
