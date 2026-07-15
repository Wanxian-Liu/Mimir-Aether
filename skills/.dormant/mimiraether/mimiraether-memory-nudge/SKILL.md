---
name: "mimiraether-memory-nudge"
description: >
  MimirAether Memory Nudge — 记忆轻推系统。通过上下文相关记忆检索、定时刷新、记忆强度追踪和遗忘模拟，主动唤醒长期记忆。包含记忆质量评分和主动提示机制。

version: "1.0.0"
category: "mimiraether"
tags:
  - memory
  - nudge
  - 记忆
  - 唤醒
  - 遗忘模拟
  - 长期记忆
---
# mimiraether-memory-nudge

## name

MimirAether Memory Nudge — 记忆轻推

## description

通过轻量级提示(Nudge)机制，主动唤醒MimirAether的长期记忆和经验。包括基于当前上下文的相关记忆检索、定时记忆刷新和遗忘模拟。

## 核心功能列表

- **上下文相关记忆唤醒**：根据当前任务检索并注入相关记忆
- **定时记忆刷新**：定期刷新重要记忆防止遗忘
- **记忆强度追踪**：记录记忆被访问的频率和重要性
- **遗忘模拟**：对低价值记忆进行渐进式遗忘，保持记忆库精简
- **记忆质量评分**：评估记忆的准确性和实用性
- **主动提示**：在适当时机主动向用户确认或提醒相关记忆

## 记忆生命周期

```
记忆创建 → 强度评分 → 定时刷新 → 衰减模拟 → 遗忘/归档
   │           │           │           │
   └─ 会话生成  └─ 0-100分  └─ 访问+1    └─ 未访问-1/周期
```

## Nudge 触发条件

### 会话启动时
启动后自动检索上次会话的关键记忆：
```
[上次: 2026-05-11] 修复了 myproject-self_evolution 中的幻影导入
[上次: 2026-05-11] Ralph Gate2 162 passed
[建议] 检查 D1 去重合并进度
```

### 任务相关时
当用户提到与记忆相关的关键词时自动唤醒：
```
用户: "继续 D1"
→ [记忆唤醒] D1 = 技能去重合并 (tdd/plan/systematic-debugging/delegate)
→ 加载上次进度: 4项合并待执行
```

### 周期性刷新
- **高频记忆** (强度>70): 每个会话开始时检查
- **中频记忆** (强度30-70): 每5个会话检查一次
- **低频记忆** (强度<30): 仅在关键词触发时检查

## 记忆强度算法

```
strength = base_score(50)
         + access_count * 2
         + recency_bonus (max 20)
         - days_since_last_access * 0.5
         - decay_if_unused (5 per idle session)
```

| 强度范围 | 状态 | 策略 |
|----------|------|------|
| 80-100 | fresh | 主动推送，无需等待触发 |
| 50-79 | warm | 关键词触发时唤醒 |
| 20-49 | cold | 仅在精确匹配时唤醒 |
| 0-19 | dormant | 存档，不主动提及 |

## 与 Context Engine 集成

```
User Message → Context Engine
                    │
                    ├─ 关键词提取
                    │     │
                    │     ▼
                    ├─ Memory Nudge ← 检索相关记忆
                    │     │
                    │     ▼
                    └─ 合并注入 → Agent Context
```

### Nudge 注入格式
```
[Memory Nudge]
· 上次类似任务: "修复幻影导入" (2026-05-11, 强度72)
· 相关技能: mimiraether-tool-triggers, mimiraether-paralysis-break
· 关键决策: 使用 agent/ 替代旧包路径
[End Nudge]
```

## 主动提示策略

| 时机 | 提示内容 |
|------|----------|
| 重复犯错 | "注意到你又在 [错误模式]，上次我们讨论过用 [方案] 避免" |
| 里程碑接近 | "D4 死链修复完成，下一步 D1 去重合并要开始吗？" |
| 知识过期 | "[某配置] 上次更新是在 30天前，可能需要刷新" |
| 新工具可用 | "有个新技能 `xxx` 可以简化这个任务" |

## 配置

```yaml
# ~/.mimir/memory_nudge.yaml
nudge:
  startup_retrieval: true
  periodic_interval_sessions: 5
  max_nudges_per_turn: 3
  
strength:
  decay_per_session: 5
  access_boost: 2
  recency_max: 20
  
thresholds:
  fresh: 80
  warm: 50
  cold: 20
```
