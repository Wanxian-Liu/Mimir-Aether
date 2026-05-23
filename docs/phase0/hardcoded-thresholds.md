# EV-Q01 — 硬编码阈值清单（2026-05-24）

> 扫描 3 模块（只读）。交叉：[compressor-overlap-audit](./compressor-overlap-audit.md)。

## 摘要

- **23** 个可调数值阈值（2026-05-21 仅计 compressor **12**）。
- **compressor 13** + **degeneration_guard 7** + **decision_ring 3**。
- AutoTuner 优先 🔴：`threshold_percent`、`_SUMMARY_FAILURE_COOLDOWN`、`loop_detection.threshold`。

## 汇总表

| 模块 | 名称 | 值 | 作用 | 优先级 |
|------|------|-----|------|:--:|
| context_compressor | `_MIN_SUMMARY_TOKENS` | 500 | 摘要最小 token | 🟡 |
| context_compressor | `_SUMMARY_RATIO` / `summary_target_ratio` | 0.20 | 摘要预算比例 | 🟡 |
| context_compressor | `_MINIMUM_CONTEXT_LENGTH` | 2000 | 最小触发上下文 | 🟡 |
| context_compressor | `_SUMMARY_TOKENS_CEILING` | 8000 | 摘要上限 | 🟡 |
| context_compressor | `_CHARS_PER_TOKEN` | 4 | token 启发估算 | 🟢 |
| context_compressor | `_SUMMARY_FAILURE_COOLDOWN` | 600s | 摘要失败冷却 | 🔴 |
| context_compressor | `_PRUNED_TOOL_MIN_CHARS` | 200 | 工具结果保留下限 | 🟢 |
| context_compressor | `threshold_percent` | 0.50 | 压缩触发使用率 | 🔴 |
| context_compressor | `protect_first_n` / `protect_last_n` | 3 / 6 | 头尾保护条数 | 🟡 |
| context_compressor | `context_length` | 1048576 | 默认窗口 | 🟡 |
| context_compressor | preflight ×0.8 | 0.8 | 预检放宽（L172） | 🟡 |
| degeneration_guard | `loop_detection.threshold` | 3 | 空转检测 | 🔴 |
| degeneration_guard | `loop_detection.window_turns` | 5 | 检测窗口 | 🟡 |
| degeneration_guard | `information_density.info_density_min` | 0.4 | 信息密度下限 | 🟡 |
| degeneration_guard | `context_quality.min_retention_rate` | 0.50 | 保留率触发压缩 | 🟡 |
| degeneration_guard | `recovery_loop.threshold` | 3 | 恢复环次数 | 🟡 |
| degeneration_guard | `recovery_loop.different_errors_min` | 2 | 异类错误下限 | 🟢 |
| decision_ring | `max_retries` | 3 | 最大重试 | 🟡 |
| decision_ring | `default_backoff_base` | 1.0 | 退避基数 | 🟢 |
| decision_ring | `max_backoff` | 60.0 | 退避上限 | 🟡 |

## vs 2026-05-21

旧稿 unmask 后数值与现网一致；本次扩面至 guard + DecisionRing。**Top3 自适应**：`threshold_percent`、冷却 600s、退化 loop threshold。
