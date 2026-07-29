# [DORMANT] mimiraether-degeneration-guard

**沉寂时间**: 2026-07-29T08:53:24.972332+00:00
**原始分类**: general
**描述**: 
**触发阈值**: 60天未触碰

---

## 技能要点

# MimirAether Degeneration Guard — 对话退化检测

**来源**: LeWM SIGReg + VoE (§3.1, §5.2) | 配置: `data/degeneration_guard.json`

## 触发条件

**硬门控**（evaluator-optimizer evaluate 步骤前必须执行）:

| 条件 | 动作 |
|------|------|
| 进入 evaluate 步骤 | 执行 loop_detection + information_density |
| 上下文压缩后 | 执行 context_quality |
| 执行结果返回后 | 执行 surprise_gate |

## 检测协议

### 1. 循环检测 (Loop Detection)

```
检查: 最近 5 轮中，同一工具调用 >= 3 次且无进展（无新文件写入/无状态变更）
触发: warn — 在评估报告中标识 ⚠️ LOOP_DETECTED
行动: 建议切换方法或请求用户介入
```

### 2. 信息密度 (Information Density)  ← SIGReg 类比

```
检查: 最近 4 轮对话是否引入了：
  - 至少 2 个不同的工具?
  - 至少 1 个文件操作?
  - 至少 1 个新的概念/实体?
触发: warn — 在评估报告中标识 ⚠️ LOW_INFORMATION_DENSITY
行动: 执行 MVA (最小可行行动) 或触发上下文重组
```

### 3. 上下文质量 (Context Quality)

```
检查: 上下文压缩后，HEAD 中的关键信息(Task/Constraints/Decisions)
      在压缩摘要中是否保留 >= 50%?
触发: compress_trigger — 强制触发上下文重组
行动: 通知用户上下文可能丢失关键信息
```

### 4. Surprise 门控 (Surprise Gate)  ← VoE 类比

```
检查: 执行结果与预期是否存在语义级偏差?
  - 表面偏差(格式/行数) → 忽略
  - 语义偏差(结果相反/断言错误/关键信息丢失) → 触发
触发: replan — 在评估报告中标识 🔴 SURPRISE_DETECTED
行动: 跳过正常 evaluate→optimize 循环，直接重规划
```

## 与 evaluator-optimizer 集成

```
在阶段 3 (Evaluate) 之前插入:

  ┌─────────────────────────┐
  │ Degeneration Guard 预检  │
  │  1. loop_detection      │
  │  2. information_density  │
  └───────────┬─────────────┘
              │
        ┌─────┴─────┐
        │ 任何触发?  │
        └─────┬─────┘
       ⚠️ 是   │   否
       │       │
   ┌───▼───┐   │
   │ 告警   │   │
   │ 建议   │   │
   └───┬───┘   │
       │       │
       └───┬───┘
           │
    ┌──────▼──────┐
    │ 继续正常     │
    │ Evaluate    │
    └─────────────┘
```

## 反模式

1. **信息密度阈值太严** → 正常探索被误判为空转
2. **surprise gate 太敏感** → 任何小偏差都触发重规划（类比 LeWM: 只对物理违规敏感）
3. **忽略循环告警** → 3次告警后仍不介入 = 门控失效

## 配置

规则配置在 `data/degeneration_guard.json`。阈值可按需调整。

---

> 此胶囊由 Skill Curator 自动生成。原始技能已移入 .dormant/。
> 调用 `skill_view("mimiraether-degeneration-guard")` 即可自动唤醒。
