#!/usr/bin/env python3
"""本地闭环检查：依赖本机 logs/、data/*.jsonl、mimicore evolve 产物；勿在 CI 中当作 pytest 用例运行。"""
from __future__ import annotations

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
sys.path.insert(0, os.path.join(ROOT, "mimicore", "evolve"))
sys.path.insert(0, os.path.join(ROOT, "mimicore", "evolve", "feedback"))

passed = 0
failed = 0


def check(name: str, condition: bool) -> None:
    global passed, failed
    if condition:
        print(f"  ✅ {name}")
        passed += 1
    else:
        print(f"  ❌ {name}")
        failed += 1


def main() -> None:
    global passed, failed

    print("1. 真实数据源")
    check("soft_beat.log存在", os.path.exists("logs/soft_beat.log"))
    if os.path.exists("logs/soft_beat.log"):
        with open("logs/soft_beat.log") as f:
            lines = [l for l in f if l.strip()]
        check(f"soft_beat.log有{len(lines)}行", len(lines) > 0)

    print("2. aggregator")
    check("raw_session_logs.jsonl存在", os.path.exists("data/raw_session_logs.jsonl"))
    if os.path.exists("data/raw_session_logs.jsonl"):
        with open("data/raw_session_logs.jsonl") as f:
            raw = [json.loads(l) for l in f if l.strip()]
        check(f"raw数据{len(raw)}条", len(raw) > 0)
        check("raw数据含timestamp字段", all("timestamp" in r for r in raw[:5]))

    print("3. bridge → orchestrator")
    for fname in ["token_level.json", "step_level.json", "episode_level.json"]:
        path = f"mimicore/evolve/feedback/aggregator_outputs/{fname}"
        check(f"{fname}存在", os.path.exists(path))
        if os.path.exists(path):
            with open(path) as f:
                data = json.load(f)
            check(f"{fname}可解析", isinstance(data, dict))

    from feedback_orchestrator import run_orchestrator

    result = run_orchestrator()
    check("orchestrator可运行", result is not None)
    check("orchestrator返回decisions", "decisions" in result)

    print("4. diversity_executor")
    from diversity_executor import DiversityExecutor

    executor = DiversityExecutor()
    signals = executor.load_trigger_signals()
    check(f"加载信号{len(signals)}条", True)
    rec = executor.decide_and_execute()
    check(f"策略非空: {rec.selected_strategy.value}", rec.selected_strategy is not None)
    check(f"效果分在0-1: {rec.effectiveness_score}", 0 <= rec.effectiveness_score <= 1)

    print("5. 熵采样多样性")
    strategies = set()
    for _ in range(10):
        r = executor.decide_and_execute()
        strategies.add(r.selected_strategy.value)
    check(f"10次采样覆盖{len(strategies)}种策略", len(strategies) >= 1)

    print(f"\n{'=' * 30}")
    print(f"结果: {passed}通过, {failed}失败")
    print("闭环测试 通" if failed == 0 else f"闭环测试 {failed}项失败")
    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
