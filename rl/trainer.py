"""
Trainer - 训练器

管理RL训练循环，支持：
- 轨迹收集
- 奖励计算
- PPO更新
- 检查点保存和恢复
- 与MimirAether Agent集成

Usage:
    trainer = Trainer(collector, calculator, optimizer)

    # 训练循环
    trainer.train(
        agent=agent,
        num_epochs=10,
        trajectories_per_epoch=32,
    )

    # 保存检查点
    trainer.save_checkpoint("checkpoint.json")

    # 恢复训练
    trainer.load_checkpoint("checkpoint.json")
    trainer.train(agent=agent, num_epochs=5)
"""

import json
import logging
import os
import signal
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional, Callable

from .collector import TrajectoryCollector, Trajectory
from .reward import RewardCalculator, RewardConfig
from .optimizer import PPOOptimizer, PPOConfig

logger = logging.getLogger(__name__)


@dataclass
class Checkpoint:
    """
    训练检查点

    保存训练状态以支持中断恢复。
    """
    checkpoint_id: str
    created_at: str
    epoch: int
    step: int
    trajectories_collected: int

    # 组件状态
    collector_state: Dict[str, Any] = field(default_factory=dict)
    optimizer_state: Dict[str, Any] = field(default_factory=dict)

    # 训练统计
    training_history: Dict[str, List[float]] = field(default_factory=dict)
    best_reward: float = -float("inf")

    # 额外元数据
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "checkpoint_id": self.checkpoint_id,
            "created_at": self.created_at,
            "epoch": self.epoch,
            "step": self.step,
            "trajectories_collected": self.trajectories_collected,
            "collector_state": self.collector_state,
            "optimizer_state": self.optimizer_state,
            "training_history": self.training_history,
            "best_reward": self.best_reward,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, d: Dict) -> "Checkpoint":
        return cls(
            checkpoint_id=d["checkpoint_id"],
            created_at=d["created_at"],
            epoch=d["epoch"],
            step=d["step"],
            trajectories_collected=d["trajectories_collected"],
            collector_state=d.get("collector_state", {}),
            optimizer_state=d.get("optimizer_state", {}),
            training_history=d.get("training_history", {}),
            best_reward=d.get("best_reward", -float("inf")),
            metadata=d.get("metadata", {}),
        )


@dataclass
class TrainingConfig:
    """
    训练配置

    Attributes:
        num_epochs: 训练轮数
        trajectories_per_epoch: 每轮的轨迹数
        eval_interval: 评估间隔（每多少步评估一次）
        checkpoint_interval: 检查点保存间隔
        checkpoint_dir: 检查点目录
        save_trajectories: 是否保存轨迹
        trajectory_dir: 轨迹保存目录
        early_stopping_patience: 早停耐心值（无改善多少轮后停止）
        early_stopping_threshold: 早停阈值
    """
    num_epochs: int = 10
    trajectories_per_epoch: int = 32
    eval_interval: int = 5
    checkpoint_interval: int = 5
    checkpoint_dir: str = "./checkpoints"
    save_trajectories: bool = True
    trajectory_dir: str = "./trajectories"
    early_stopping_patience: int = 10
    early_stopping_threshold: float = 1e-4

    def to_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in self.__dict__.items()}


class Trainer:
    """
    RL训练器

    管理完整的训练流程：
    1. 从Agent收集轨迹
    2. 计算奖励
    3. PPO更新
    4. 检查点管理

    Usage:
        from rl import Trainer, TrajectoryCollector, RewardCalculator, PPOOptimizer

        collector = TrajectoryCollector()
        calculator = RewardCalculator()
        optimizer = PPOOptimizer()
        trainer = Trainer(collector, calculator, optimizer)

        # 训练
        trainer.train(agent=my_agent, num_epochs=10)

        # 保存/恢复
        trainer.save_checkpoint("my_checkpoint.json")
        trainer.load_checkpoint("my_checkpoint.json")
    """

    def __init__(
        self,
        collector: Optional[TrajectoryCollector] = None,
        calculator: Optional[RewardCalculator] = None,
        optimizer: Optional[PPOOptimizer] = None,
        config: Optional[TrainingConfig] = None,
    ):
        self.collector = collector or TrajectoryCollector()
        self.calculator = calculator or RewardCalculator()
        self.optimizer = optimizer or PPOOptimizer()
        self.config = config or TrainingConfig()

        # 训练状态
        self.current_epoch = 0
        self.current_step = 0
        self.total_trajectories = 0
        self._is_training = False
        self._should_stop = False

        # 历史
        self.training_history: Dict[str, List[float]] = {
            "epoch_rewards": [],
            "epoch_losses": [],
            "trajectory_rewards": [],
        }

        # 创建目录
        Path(self.config.checkpoint_dir).mkdir(parents=True, exist_ok=True)
        if self.config.save_trajectories:
            Path(self.config.trajectory_dir).mkdir(parents=True, exist_ok=True)

        # 注册信号处理（支持Ctrl+C优雅停止）
        self._register_signal_handlers()

        logger.info(f"Trainer initialized with config: {self.config.to_dict()}")

    def _register_signal_handlers(self):
        """注册信号处理器，支持优雅中断"""
        def handle_signal(signum, frame):
            logger.warning(f"Received signal {signum}, will stop after current epoch...")
            self._should_stop = True

        try:
            signal.signal(signal.SIGINT, handle_signal)
            signal.signal(signal.SIGTERM, handle_signal)
        except Exception as e:
            logger.warning(f"Could not register signal handlers: {e}")

    def train(
        self,
        agent: Any,
        num_epochs: Optional[int] = None,
        trajectories_per_epoch: Optional[int] = None,
        eval_fn: Optional[Callable[[int, List[Trajectory]], Dict]] = None,
        progress_callback: Optional[Callable[[int, int, Dict], None]] = None,
    ) -> Dict[str, Any]:
        """
        执行训练循环

        Args:
            agent: MimirAether Agent实例
            num_epochs: 训练轮数（覆盖配置）
            trajectories_per_epoch: 每轮轨迹数（覆盖配置）
            eval_fn: 评估函数 (epoch, trajectories) -> metrics
            progress_callback: 进度回调 (epoch, step, metrics) -> None

        Returns:
            训练结果统计
        """
        num_epochs = num_epochs or self.config.num_epochs
        trajectories_per_epoch = trajectories_per_epoch or self.config.trajectories_per_epoch

        self._is_training = True
        self._should_stop = False

        logger.info(f"Starting training: {num_epochs} epochs, {trajectories_per_epoch} trajectories/epoch")

        try:
            for epoch in range(self.current_epoch, num_epochs):
                if self._should_stop:
                    logger.info("Training interrupted, saving checkpoint...")
                    self.save_checkpoint()
                    break

                self.current_epoch = epoch
                epoch_metrics = self._train_epoch(
                    agent, epoch, trajectories_per_epoch, eval_fn
                )

                # 记录历史
                self.training_history["epoch_rewards"].append(
                    epoch_metrics.get("mean_reward", 0.0)
                )
                self.training_history["epoch_losses"].append(
                    epoch_metrics.get("mean_loss", 0.0)
                )

                # 进度回调
                if progress_callback:
                    progress_callback(epoch, self.current_step, epoch_metrics)

                logger.info(
                    f"Epoch {epoch}/{num_epochs}: "
                    f"mean_reward={epoch_metrics.get('mean_reward', 0):.4f}, "
                    f"mean_loss={epoch_metrics.get('mean_loss', 0):.4f}, "
                    f"trajectories={epoch_metrics.get('trajectories_collected', 0)}"
                )

                # 检查点
                if (epoch + 1) % self.config.checkpoint_interval == 0:
                    self.save_checkpoint()

                # 早停检查
                if self._check_early_stopping(epoch):
                    logger.info("Early stopping triggered")
                    break

        finally:
            self._is_training = False

        # 保存最终检查点
        self.save_checkpoint()

        return {
            "final_epoch": self.current_epoch,
            "total_trajectories": self.total_trajectories,
            "total_steps": self.current_step,
            "training_history": self.training_history,
        }

    def _train_epoch(
        self,
        agent: Any,
        epoch: int,
        num_trajectories: int,
        eval_fn: Optional[Callable],
    ) -> Dict[str, Any]:
        """
        训练单个epoch

        1. 从Agent收集轨迹
        2. 计算奖励
        3. PPO更新
        4. 可选评估
        """
        epoch_trajectories = []
        epoch_rewards = []
        epoch_losses = []

        for traj_idx in range(num_trajectories):
            if self._should_stop:
                break

            self.current_step += 1

            # 收集轨迹
            trajectory = self._collect_trajectory(agent)
            if trajectory is None:
                continue

            # 计算奖励
            trajectory = self.calculator.calculate(trajectory)

            # 计算GAE回报
            trajectory.compute_returns(
                gamma=self.optimizer.config.gamma,
                lambda_=self.optimizer.config.lambda_,
            )

            # 添加到收集器
            self.collector.add_trajectory(trajectory)
            self.total_trajectories += 1
            epoch_trajectories.append(trajectory)
            epoch_rewards.append(trajectory.total_reward)

            # 训练轨迹记录
            self.training_history["trajectory_rewards"].append(trajectory.total_reward)

        # 批量PPO更新
        if epoch_trajectories:
            update_stats = self.optimizer.update(epoch_trajectories)
            epoch_losses.append(update_stats.get("total_loss", 0.0))

        # 评估
        eval_metrics = {}
        if eval_fn and (epoch + 1) % self.config.eval_interval == 0:
            eval_metrics = eval_fn(epoch, epoch_trajectories)

        return {
            "mean_reward": sum(epoch_rewards) / len(epoch_rewards) if epoch_rewards else 0.0,
            "mean_loss": sum(epoch_losses) / len(epoch_losses) if epoch_losses else 0.0,
            "trajectories_collected": len(epoch_trajectories),
            "total_trajectories": self.total_trajectories,
            **eval_metrics,
        }

    def _collect_trajectory(self, agent: Any) -> Optional[Trajectory]:
        """
        从Agent收集单条轨迹

        这是一个示例实现，根据实际Agent接口调整。
        支持两种模式：
        1. Agent有chat()方法
        2. Agent有run_conversation()方法
        """
        try:
            # 检查Agent接口
            if hasattr(agent, "run_conversation"):
                # 使用run_conversation获取完整轨迹
                # 需要外部提供任务或使用预定义任务池
                task = self._sample_task()
                result = agent.run_conversation(task)

                # 从对话历史构建轨迹
                if hasattr(agent, "conversation_history"):
                    messages = [
                        {
                            "role": m.role.value if hasattr(m.role, "value") else str(m.role),
                            "content": m.content,
                        }
                        for m in agent.conversation_history
                    ]
                else:
                    messages = [{"role": "user", "content": task}]

                outcome = "success" if result and len(result) > 10 else "partial"
                model = getattr(agent, "model", "unknown")

                return self.collector.add_from_messages(
                    messages=messages,
                    task=task,
                    outcome=outcome,
                    model=model,
                    platform=getattr(agent, "platform", "unknown"),
                )
            elif hasattr(agent, "chat"):
                # 单轮对话模式
                task = self._sample_task()
                result = agent.chat(task)

                outcome = "success" if result and len(result) > 10 else "partial"

                return self.collector.add_turn(
                    user_message=task,
                    assistant_message=result or "",
                    outcome=outcome,
                    model=getattr(agent, "model", "unknown"),
                )
            else:
                logger.warning("Agent does not have chat() or run_conversation() method")
                return None

        except Exception as e:
            logger.error(f"Error collecting trajectory: {e}")
            return None

    def _sample_task(self) -> str:
        """
        采样任务

        这是一个占位符，实际应用中应该从任务池中采样。
        """
        tasks = [
            "What is the capital of France?",
            "Explain quantum entanglement in simple terms.",
            "Write a Python function to calculate fibonacci numbers.",
            "What are the main benefits of renewable energy?",
            "Summarize the plot of Romeo and Juliet.",
        ]
        import random
        return random.choice(tasks)

    def _check_early_stopping(self, epoch: int) -> bool:
        """检查是否应该早停"""
        if epoch < self.config.early_stopping_patience:
            return False

        recent_rewards = self.training_history["epoch_rewards"][
            -self.config.early_stopping_patience :
        ]
        if len(recent_rewards) < 2:
            return False

        # 检查是否有改善
        last_reward = recent_rewards[-1]
        best_reward = max(recent_rewards)
        current_best = max(self.training_history["epoch_rewards"])

        if last_reward >= current_best - self.config.early_stopping_threshold:
            return True

        return False

    # ========================================================================
    # 检查点管理
    # ========================================================================

    def save_checkpoint(self, path: Optional[str] = None):
        """
        保存检查点

        支持中断恢复。保存所有必要的状态：
        - 当前epoch和step
        - 收集器状态
        - 优化器状态
        - 训练历史
        """
        if path is None:
            path = os.path.join(
                self.config.checkpoint_dir,
                f"checkpoint_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            )

        checkpoint = Checkpoint(
            checkpoint_id=str(uuid.uuid4()),
            created_at=datetime.now().isoformat(),
            epoch=self.current_epoch,
            step=self.current_step,
            trajectories_collected=self.total_trajectories,
            training_history=dict(self.training_history),
            best_reward=max(self.training_history.get("epoch_rewards", [-float("inf")])),
        )

        # 保存收集器统计
        checkpoint.collector_state = self.collector.get_statistics()

        # 保存优化器状态
        optimizer_path = path.replace(".json", "_optimizer.json")
        self.optimizer.save(optimizer_path)
        checkpoint.optimizer_state = {"optimizer_path": optimizer_path}

        # 保存轨迹
        if self.config.save_trajectories:
            traj_path = os.path.join(
                self.config.trajectory_dir,
                f"trajectories_epoch{self.current_epoch}.jsonl",
            )
            self.collector.export_jsonl(traj_path)
            checkpoint.metadata["trajectory_path"] = traj_path

        with open(path, "w") as f:
            json.dump(checkpoint.to_dict(), f, indent=2)

        logger.info(f"Saved checkpoint to {path}")
        return path

    def load_checkpoint(self, path: str):
        """
        加载检查点

        恢复训练状态。
        """
        with open(path, "r") as f:
            data = json.load(f)

        checkpoint = Checkpoint.from_dict(data)

        self.current_epoch = checkpoint.epoch
        self.current_step = checkpoint.step
        self.total_trajectories = checkpoint.trajectories_collected
        self.training_history = dict(checkpoint.training_history)

        # 加载优化器状态
        optimizer_path = checkpoint.optimizer_state.get("optimizer_path")
        if optimizer_path and os.path.exists(optimizer_path):
            self.optimizer.load(optimizer_path)

        # 加载轨迹
        traj_path = checkpoint.metadata.get("trajectory_path")
        if traj_path and os.path.exists(traj_path):
            self.collector.import_jsonl(traj_path)

        logger.info(
            f"Loaded checkpoint from {path}: "
            f"epoch={self.current_epoch}, step={self.current_step}, "
            f"trajectories={self.total_trajectories}"
        )

    # ========================================================================
    # 与Agent集成
    # ========================================================================

    def attach_to_agent(self, agent: Any):
        """
        将RL系统附加到Agent

        让Agent自动记录轨迹用于训练。

        这会修改Agent的行为：
        - 每次对话后自动记录轨迹
        - 可选：基于RL更新调整Agent行为

        Args:
            agent: MimirAether Agent实例
        """
        if hasattr(agent, "run_conversation"):
            original_run = agent.run_conversation

            async def tracked_run(user_message: str) -> str:
                result = await original_run(user_message)

                # 记录轨迹
                if hasattr(agent, "conversation_history"):
                    messages = [
                        {
                            "role": m.role.value if hasattr(m.role, "value") else str(m.role),
                            "content": m.content,
                        }
                        for m in agent.conversation_history
                    ]
                    outcome = "success" if result and len(result) > 10 else "partial"
                    traj = self.collector.add_from_messages(
                        messages=messages,
                        task=user_message[:200],
                        outcome=outcome,
                        model=getattr(agent, "model", "unknown"),
                    )
                    traj = self.calculator.calculate(traj)
                    self.collector.add_trajectory(traj)
                    self.total_trajectories += 1

                return result

            agent.run_conversation = tracked_run
            logger.info("Attached RL tracker to agent (run_conversation)")

        if hasattr(agent, "chat"):
            original_chat = agent.chat

            async def tracked_chat(message: str) -> str:
                result = await original_chat(message)

                # 记录轨迹
                outcome = "success" if result and len(result) > 10 else "partial"
                traj = self.collector.add_turn(
                    user_message=message,
                    assistant_message=result or "",
                    outcome=outcome,
                    model=getattr(agent, "model", "unknown"),
                )
                traj = self.calculator.calculate(traj)
                self.collector.add_trajectory(traj)
                self.total_trajectories += 1

                return result

            agent.chat = tracked_chat
            logger.info("Attached RL tracker to agent (chat)")

    def get_status(self) -> Dict[str, Any]:
        """获取训练状态"""
        return {
            "is_training": self._is_training,
            "current_epoch": self.current_epoch,
            "current_step": self.current_step,
            "total_trajectories": self.total_trajectories,
            "collector_stats": self.collector.get_statistics(),
            "reward_stats": self.calculator.get_statistics(),
            "training_history": {
                k: v[-10:] for k, v in self.training_history.items()
            },
        }
