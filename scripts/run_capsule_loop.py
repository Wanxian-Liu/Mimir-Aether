#!/usr/bin/env python3
import sys, os, json
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)
from scripts.task_loop_config import TaskLoopConfig
from scripts.task_loop import run as taskloop_run
from scripts.strategy_capsule import capsule_strategy
CONFIG_PATH = os.path.join(REPO_ROOT, "mimicore", "generator_config.json")

def main():
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--rounds", type=int, default=6)
    p.add_argument("--target", type=float, default=0.85)
    args = p.parse_args()
    with open(CONFIG_PATH) as f:
        initial = f.read()
    config = TaskLoopConfig(
        task="优化 GDI", eval_cmd="python3 scripts/gen_and_score.py",
        target_score=args.target, max_rounds=args.rounds, max_time=300,
        eval_timeout=60, no_go=["不改 gdi_scorer.py","不改 TEST_INPUTS"],
        workdir=REPO_ROOT, min_delta=0.001,
    )
    result = taskloop_run(config, strategy_fn=capsule_strategy)
    with open(CONFIG_PATH, "w") as f:
        f.write(initial)
    print("\nbest={:.4f} R{} stop={}".format(
        result.best_score, result.best_round, result.stop_reason))
    return 0

if __name__ == "__main__":
    sys.exit(main())
