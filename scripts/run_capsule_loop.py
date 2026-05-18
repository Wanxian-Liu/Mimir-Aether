#!/usr/bin/env python3
"""
胶囊 GDI 元级自改进 — 运行入口

用法:
    python3 scripts/run_capsule_loop.py [--rounds N] [--target T]

BACKLOG #6: 元级自改进 — capsule GDI≥70
"""

import sys
import os

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)

from scripts.task_loop_config import TaskLoopConfig
from scripts.task_loop import run as taskloop_run
from scripts.strategy_capsule import capsule_strategy, read_config, write_config


def main():
    import argparse
    parser = argparse.ArgumentParser(description="胶囊 GDI 元级自改进")
    parser.add_argument("--rounds", type=int, default=10, help="最大轮次")
    parser.add_argument("--target", type=float, default=0.80, help="目标 GDI")
    parser.add_argument("--time", type=int, default=600, help="总时间预算(秒)")
    args = parser.parse_args()

    # 保存初始配置（运行结束后恢复）
    initial_config = read_config()

    config = TaskLoopConfig(
        task="优化 capsule 生成质量，提升 GDI 评分到 0.80",
        eval_cmd="python3 scripts/gen_and_score.py",
        target_score=args.target,
        max_rounds=args.rounds,
        max_time=args.time,
        eval_timeout=60,
        no_go=[
            "不要改 gdi_scorer.py",
            "不要改 gen_and_score.py 的测试用例",
            "不要改 capsule_generator.py 的核心逻辑",
        ],
        workdir=REPO_ROOT,
        min_delta=0.001,
    )

    result = taskloop_run(config, strategy_fn=capsule_strategy)

    # 如果有改进，保留最佳配置；否则恢复原始
    if result.best_score > 0.734:  # 基线以上
        print(f"\n✅ 最佳 GDI: {result.best_score:.4f} (第{result.best_round}轮)")
    else:
        write_config(initial_config)
        print(f"\n⚠️ 无改进，已恢复初始配置")

    return 0


if __name__ == "__main__":
    sys.exit(main())
