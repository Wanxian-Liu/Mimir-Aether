#!/usr/bin/env python3
"""BACKLOG #6: capsule TaskLoop — 真模块 + GDI 1-hop 验证

集成:
  - #1: belief_callback (enhanced 模式分析 / LLM Predict-then-Attribute 可选)
  - #2: regression_cmd (gate 通过后跑 tier0 防回归)
  - #3: results.tsv 不 commit (task_loop.py git_commit 内置)
  - strategy: capsule 映射表修改
"""
import sys, os, json, argparse
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)
from scripts.task_loop_config import TaskLoopConfig
from scripts.task_loop import run as taskloop_run
from scripts.strategy_capsule import capsule_strategy
from scripts.belief_capsule import make_belief_callback
CONFIG_PATH = os.path.join(REPO_ROOT, "mimicore", "generator_config.json")


def main():
    p = argparse.ArgumentParser(description="capsule GDI TaskLoop")
    p.add_argument("--rounds", type=int, default=8)
    p.add_argument("--target", type=float, default=0.85)
    p.add_argument("--time", type=int, default=600)
    args = p.parse_args()

    with open(CONFIG_PATH) as f:
        initial = f.read()

    config = TaskLoopConfig(
        task="优化 capsule GDI 分数 (五维评分含 content_richness)",
        eval_cmd="python3 scripts/gen_and_score.py",
        target_score=args.target,
        max_rounds=args.rounds,
        max_time=args.time,
        eval_timeout=60,
        no_go=["不改 gdi_scorer.py", "不改 TEST_INPUTS", "不改 eval_capsule_gdi.py"],
        workdir=REPO_ROOT,
        min_delta=0.001,
        regression_cmd="./run_ralph_tier0.sh",       # #2: 防回归
        belief_callback=make_belief_callback(),      # #1: LLM/增强 信念
    )

    result = taskloop_run(config, strategy_fn=capsule_strategy)

    # 恢复 config（TaskLoop 修改的是 generator_config.json）
    with open(CONFIG_PATH, "w") as f:
        f.write(initial)

    # 信念持久化 (beliefs.md 在 REPO_ROOT)
    beliefs_path = os.path.join(REPO_ROOT, "data", "beliefs.md")
    if hasattr(config, 'belief_callback') and config.belief_callback:
        # 信念已在 loop 中通过 belief_callback 更新到 BeliefsBuffer
        pass

    print("\nbest={:.4f} R{} stop={}".format(
        result.best_score, result.best_round, result.stop_reason))
    return 0


if __name__ == "__main__":
    sys.exit(main())
