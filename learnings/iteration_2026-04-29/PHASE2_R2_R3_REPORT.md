# Phase 2 R2/R3: 根因分析 + 实施修复

## 执行时间
2026-04-29 04:05 GMT+8

## 根因分析

### 问题1: threshold_percent过高
- **原因**: 默认值0.85导致压缩触发过晚
- **影响**: 长对话可能超出上下文限制
- **修复**: 改为0.50，与Hermes一致

### 问题2: tail_token_budget固定
- **原因**: 没有根据threshold_tokens动态计算
- **影响**: 浪费上下文空间或压缩不足
- **修复**: `tail_token_budget = int(threshold_tokens * summary_target_ratio)`

### _previous_summary
- **状态**: ✅ 已实现，无需修改

## 修复内容

```python
# 修改前
threshold_percent: float = 0.85
tail_token_budget: int = 4000

# 修改后
threshold_percent: float = 0.50  # Hermes对齐
tail_token_budget: int = None    # 动态计算
```

## 验证结果

```
threshold_percent: 0.5
threshold_tokens: 4000
tail_token_budget: 800 (动态)
summary_target_ratio: 0.2
```

## R4准备: 功能验证
