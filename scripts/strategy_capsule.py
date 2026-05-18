#!/usr/bin/env python3
"""
胶囊 GDI 优化策略 — TaskLoop 元级自改进

修改 generator_config.json 中的调优参数，
用 gen_and_score.py 评测，追求 GDI ≥ 0.80。

策略:
- 每次改 1-2 个布尔开关或数值
- 不改 gdi_scorer.py（评测神圣）
"""

import json
import random
import os

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(REPO_ROOT, "mimicore", "generator_config.json")


def read_config():
    with open(CONFIG_PATH) as f:
        return json.load(f)


def write_config(config: dict):
    with open(CONFIG_PATH, "w") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)


def capsule_strategy(rounds, best_score, task_config):
    """
    TaskLoop 策略函数签名:
      rounds: list[RoundState] — 历史轮次
      best_score: float — 当前最佳分数
      task_config: TaskLoopConfig — 任务配置

    Returns: (hypothesis, changes_dict, error)
    """
    config = read_config()

    # 可调参数空间
    bool_params = [
        ("content.include_note_section", "content", "include_note_section"),
        ("content.include_tags_section", "content", "include_tags_section"),
        ("structure.add_summary_section", "structure", "add_summary_section"),
        ("structure.add_prerequisites_section", "structure", "add_prerequisites_section"),
        ("tags.auto_tags", "tags", "auto_tags"),
    ]
    num_params = [
        ("metadata.task_usage_count", "metadata", "task_usage_count", [5, 10, 15, 20, 30]),
        ("metadata.retrieval_count", "metadata", "retrieval_count", [10, 30, 50, 100, 200]),
        ("metadata.update_count", "metadata", "update_count", [1, 3, 5, 10, 20]),
        ("content.max_title_length", "content", "max_title_length", [40, 50, 60, 80, 100]),
    ]

    # 选一个参数调
    if random.random() < 0.5:
        # 调布尔
        name, section, key = random.choice(bool_params)
        old_val = config[section][key]
        new_val = not old_val
        config[section][key] = new_val
        hypothesis = f"toggle {name} = {new_val}"
    else:
        # 调数值
        name, section, key, options = random.choice(num_params)
        old_val = config[section][key]
        options_filtered = [o for o in options if o != old_val]
        new_val = random.choice(options_filtered) if options_filtered else old_val
        config[section][key] = new_val
        hypothesis = f"set {name} = {new_val} (was {old_val})"

    write_config(config)

    # 返回改动
    changes = {"mimicore/generator_config.json": json.dumps(config, indent=2, ensure_ascii=False)}
    return hypothesis, changes, None
