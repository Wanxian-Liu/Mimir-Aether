# Phase 2 R1: context_compressor修复 - 沙盒执行

## 执行时间
2026-04-29 04:02 GMT+8

## 问题
1. `threshold_percent = 0.85` 但Hermes使用 `0.50`
2. `tail_token_budget` 固定4000，但应该动态计算

## 当前状态

### MimirAether (修复前)
```python
threshold_percent: float = 0.85  # 85%
tail_token_budget: int = 4000    # 固定
protect_last_n: int = 6
```

### Hermes (目标)
```python
threshold_percent: float = 0.50  # 50%
tail_token_budget = int(threshold_tokens * summary_target_ratio)  # 动态
protect_last_n: int = 20
```

## 发现

### 1. threshold_percent
- MimirAether: 0.85 (line 70)
- Hermes: 0.50 (line 113)

### 2. tail_token_budget
- MimirAether: 固定4000 (line 73)
- Hermes: 动态计算 `int(self.threshold_tokens * self.summary_target_ratio)` (line 145-146)

### 3. _previous_summary
- **已实现** - MimirAether已有此功能 (line 103, 301, 309, 311, 595, 731)

## R2准备: 根因分析
