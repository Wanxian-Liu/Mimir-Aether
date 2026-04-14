"""
MimirAether RL Training Framework

Phase 6: Reinforcement Learning Training System

Core Components:
- TrajectoryCollector: Collects agent behavior trajectories from conversations
- RewardCalculator: Computes rewards based on outcomes
- PPOOptimizer: Simplified PPO optimizer for policy updates
- Trainer: Manages the training loop with checkpoint/resume support

Usage:
    from rl import TrajectoryCollector, RewardCalculator, PPOOptimizer, Trainer

    collector = TrajectoryCollector()
    calculator = RewardCalculator(reward_fn=my_reward_fn)
    optimizer = PPOOptimizer(model_dim=4096)
    trainer = Trainer(collector, calculator, optimizer)

    # Collect trajectories
    collector.add_turn(user_msg, assistant_msg, tool_calls, outcome)

    # Train
    trainer.train(num_epochs=10)
"""

from .collector import TrajectoryCollector, Trajectory, TrajectoryStep
from .reward import RewardCalculator, RewardConfig
from .optimizer import PPOOptimizer, PPOConfig
from .trainer import Trainer, TrainingConfig, Checkpoint

__all__ = [
    "TrajectoryCollector",
    "Trajectory",
    "TrajectoryStep",
    "RewardCalculator",
    "RewardConfig",
    "PPOOptimizer",
    "PPOConfig",
    "Trainer",
    "TrainingConfig",
    "Checkpoint",
]
