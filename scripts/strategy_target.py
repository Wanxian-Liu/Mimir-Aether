"""
TaskLoop 策略 — 随机爬山 (Randomized Hill Climbing)

修改 target_config.json 的 4 个参数，目标是提高 taskloop_target.py 的分数。

策略:
  - 前 3 轮: 大范围探索 (±0.3)
  - 之后: 精细调整 (±0.1)
  - 如果连续失败: 随机跳跃 (尝试全新区域)
  - 如果接近最优 (score > 85): 微调 (±0.02)

返回: (hypothesis, changes_dict, error)
"""

import json
import random
from pathlib import Path


PARAM_KEYS = ["alpha", "beta", "gamma", "threshold"]


def load_current(workdir: str) -> dict:
    path = Path(workdir) / "target_config.json"
    if path.exists():
        return json.loads(path.read_text())
    return {k: 0.5 for k in PARAM_KEYS}


def save_config(workdir: str, config: dict):
    path = Path(workdir) / "target_config.json"
    path.write_text(json.dumps(config, indent=2))


def nudge(value: float, max_delta: float) -> float:
    """随机扰动，钳制到 [0, 1]"""
    delta = random.uniform(-max_delta, max_delta)
    return round(max(0.0, min(1.0, value + delta)), 3)


def strategy(rounds, best_score, config):
    """主策略函数 — TaskLoop 每轮调用"""
    current = load_current(config.workdir)
    num_rounds = len(rounds)

    # 阶段判断
    if best_score > 95:
        max_delta = 0.02  # 极精细
    elif best_score > 85:
        max_delta = 0.05  # 精细
    elif num_rounds < 3:
        max_delta = 0.30  # 大范围探索
    else:
        max_delta = 0.10  # 常规

    # 如果最近连续失败，跳跃
    recent_fails = sum(1 for r in rounds[-3:] if not r.passed)
    if recent_fails >= 2:
        # 随机跳跃到全新位置
        key = random.choice(PARAM_KEYS)
        old_val = current.get(key, 0.5)
        new_val = round(random.uniform(0.0, 1.0), 3)
        hypothesis = f"跳跃: {key} {old_val}→{new_val}"
        current[key] = new_val
    else:
        # 正常微调
        key = random.choice(PARAM_KEYS)
        old_val = current.get(key, 0.5)
        new_val = nudge(old_val, max_delta)
        hypothesis = f"调整 {key}: {old_val} → {new_val}"

    changes = {"target_config.json": json.dumps(current, indent=2)}
    return hypothesis, changes, None
