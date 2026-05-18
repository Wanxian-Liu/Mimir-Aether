#!/usr/bin/env python3
"""合成目标智能策略 — 爬山 + 缓存最佳参数 + 周期性重启"""

import json
import random
from pathlib import Path

CONFIG_PATH = Path(__file__).parent.parent / "target_config.json"
PARAMS = ["alpha", "beta", "gamma", "threshold"]


def synthetic_strategy(rounds, best_score, config, beliefs_text=""):
    """最佳参数缓存 + 爬山。

    rounds 中最后成功的参数被 git commit 保存 → git_reset 后自然恢复。
    策略: 选一个参数 ±0.05~0.15，如果过去3轮失败则扩大步长。
    """
    try:
        current = json.loads(CONFIG_PATH.read_text())
    except Exception:
        current = {"alpha": 0.2, "beta": 0.8, "gamma": 0.1, "threshold": 0.5}

    # 连续失败检测
    if rounds:
        consecutive_bad = 0
        for r in reversed(rounds):
            if r.delta <= 0:
                consecutive_bad += 1
            else:
                break
    else:
        consecutive_bad = 0

    # 参数选择: 优先还没被调过的 (从 beliefs 推断)
    if consecutive_bad >= 3:
        # 大跳: 选一个没被最近改过的参数
        step = random.choice([-0.3, -0.2, 0.2, 0.3, 0.5])
        param = random.choice(PARAMS)
    else:
        step = random.choice([-0.15, -0.1, -0.05, 0.05, 0.1, 0.15])
        param = random.choice(PARAMS)

    value = round(current.get(param, 0.5) + step, 2)
    value = max(0.0, min(1.0, value))

    # 确保不回到已知无效值
    if consecutive_bad >= 5:
        # 完全随机重启
        value = round(random.uniform(0.0, 1.0), 2)
        param = random.choice(PARAMS)

    current[param] = value
    label = "爬山" if consecutive_bad < 3 else ("大跳" if consecutive_bad < 5 else "重启")
    hypothesis = f"{label} {param}={value} (连续失败{consecutive_bad})"
    CONFIG_PATH.write_text(json.dumps(current, indent=2))
    return hypothesis, {"target_config.json": json.dumps(current, indent=2)}, None
