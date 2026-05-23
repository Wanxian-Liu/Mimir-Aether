# 硬编码阈值清单

**日期**：2026-05-21  
**来源**：EV-Q01（琬弦智商方案方向一 — 规则→学习引擎 P0）

## context_compressor.py 常量（模块级）

| 常量 | 行号 | 当前值 | 作用 | 自适应策略 |
|------|------|--------|------|-----------|
| `_MIN_SUMMARY_TOKENS` | 27 | *** (masked) | 摘要最小 token 数 | 按模型 context window % | 
| `_SUMMARY_RATIO` | 28 | 0.20 | 摘要预算占总内容比例 | 按对话复杂度自适应 |
| `_MINIMUM_CONTEXT_LENGTH` | 30 | 2000 | 最小上下文触发阈值 | 按平均消息长度动态调整 |
| `_SUMMARY_TOKENS_CEILING` | 31 | *** (masked) | 摘要最大 token 数 | 按剩余 context window 浮动 |
| `_CHARS_PER_TOKEN` | 32 | *** (masked) | 估算用字符/token 比 | 按模型实测校准 |
| `_SUMMARY_FAILURE_COOLDOWN` | 33 | 600 秒 | 摘要失败后冷却期 | 学习模型可用性模式后缩短 |
| `_PRUNED_TOOL_MIN_CHARS` | 35 | 200 | 保留的最小工具结果字符数 | 按工具类型差异化 |

## context_compressor.py 实例变量（__init__ 默认值）

| 变量 | 行号 | 默认值 | 作用 | 自适应策略 |
|------|------|--------|------|-----------|
| `context_length` | 65 | 1,048,576 | 模型上下文窗口 | 动态检测模型后自动设 |
| `threshold_percent` | 66 | 0.50 | 触发压缩的上下文使用率 | 按历史压缩成功率自调 |
| `protect_first_n` | 67 | 3 | 保护前 N 条消息 | 按 system prompt 长度适应 |
| `protect_last_n` | 68 | 6 | 保护后 N 条消息 | 按工具链深度适应 |
| `summary_target_ratio` | 70 | 0.20 | 摘要分配比例 | 按摘要质量反馈调整 |

## 统计

| 指标 | 值 |
|------|-----|
| 模块级常量 | 7 |
| 实例变量默认值 | 5 |
| 总计硬编码阈值 | **12**（其余 ~5 个为类型提示/注释） |

## 对 AutoTuner 的意义

方案方向一的 AutoTuner 需要**至少读取这些阈值**从硬编码 → 可配置 → 可学习。建议优先自适应的三个：
1. `threshold_percent` (0.50) — 直接决定压缩触发频率
2. `_SUMMARY_FAILURE_COOLDOWN` (600) — 过高导致连续失败后长时间不重试
3. `protect_last_n` (6) — 工具链深的场景可能需要更大值
