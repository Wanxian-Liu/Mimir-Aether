"""
TaskLoop 合成目标 — 运行器

用法:  python3 scripts/run_target_loop.py
"""

import sys
from pathlib import Path

# 确保可以 import scripts 下的模块
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.task_loop_config import TaskLoopConfig
from scripts.task_loop import run
from scripts.strategy_target import strategy


def main():
    config = TaskLoopConfig(
        task="优化合成目标 — 找最优参数组合 (alpha=0.7, beta=0.3, gamma=0.5, threshold=0.8)",
        eval_cmd="python3 scripts/taskloop_target.py",
        target_score=95.0,
        max_rounds=15,
        max_time=300,
        eval_timeout=30,
        no_go=[],
        workdir=".",
    )

    # 重置默认配置到远离最优值的位置
    import json
    default = {"alpha": 0.2, "beta": 0.8, "gamma": 0.1, "threshold": 0.5}
    Path("target_config.json").write_text(json.dumps(default, indent=2))

    print("=" * 60)
    print("  TaskLoop 合成目标验证")
    print("  目标: 从 (0.2, 0.8, 0.1, 0.5) → (0.7, 0.3, 0.5, 0.8)")
    print("  满分: 100.0  目标: 95.0  轮次上限: 15")
    print("=" * 60)

    result = run(config, strategy_fn=strategy)

    print(f"\n最终分数: {result.best_score:.4f} (第{result.best_round}轮)")
    print(f"停止原因: {result.stop_reason.value}")

    return 0 if result.best_score >= 95 else 1


if __name__ == "__main__":
    sys.exit(main())
