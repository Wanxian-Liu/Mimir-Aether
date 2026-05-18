"""
TaskLoop 合成验证目标 — 有真因果链的优化问题

用法:  python3 scripts/taskloop_target.py
       → 读取 target_config.json 的 4 个参数
       → 输出分数 (stdout 末行)

参数空间: alpha, beta, gamma, threshold (范围 0.0~1.0)
最优解:   alpha=0.7, beta=0.3, gamma=0.5, threshold=0.8
满分:     100.0

1-hop 链路: 改 target_config.json → 跑本脚本 → 分数立即响应
"""

import json
import sys
from pathlib import Path


# 最优值 — 策略不应该知道这些
OPTIMAL = {
    "alpha": 0.7,
    "beta": 0.3,
    "gamma": 0.5,
    "threshold": 0.8,
}


def compute_score(config: dict) -> float:
    """MSE 距离 → 0~100 分数。满分 = 所有参数匹配最优值"""
    keys = list(OPTIMAL.keys())
    mse = 0.0
    for k in keys:
        actual = float(config.get(k, 0.5))
        # 钳制到 [0, 1]
        actual = max(0.0, min(1.0, actual))
        mse += (actual - OPTIMAL[k]) ** 2
    mse /= len(keys)

    # 加分项: 参数之间的交互 — beta 应 < alpha
    bonus = 0.0
    if config.get("beta", 0) < config.get("alpha", 0):
        bonus = 5.0

    # 惩罚: threshold 太接近 0.5 (鼓励极端值)
    penalty = 0.0
    thr = float(config.get("threshold", 0.5))
    if 0.4 < thr < 0.6:
        penalty = 3.0

    raw = 100.0 * (1.0 - mse)
    return raw + bonus - penalty


def main():
    config_path = Path(__file__).parent.parent / "target_config.json"

    if not config_path.exists():
        # 默认配置 — 故意远离最优值
        default = {"alpha": 0.2, "beta": 0.8, "gamma": 0.1, "threshold": 0.5}
        config_path.write_text(json.dumps(default, indent=2))
        print(f"[init] 已创建默认配置: {config_path}", file=sys.stderr)
        config = default
    else:
        config = json.loads(config_path.read_text())

    score = compute_score(config)
    # 只有分数在 stdout 末行 — 这是 TaskLoop 的约定
    print(f"{score:.4f}")


if __name__ == "__main__":
    main()
