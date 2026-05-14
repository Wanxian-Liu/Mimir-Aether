# MimirAether 超参数审计

> **对标 LeWM**: 类 JEPA 训练需 6 个超参数（多损失项、EMA、预训练编码器、辅助监督…），LeWM 用 SIGReg 将有效超参数从 6 → 1。本文审计 MimirAether 的同等问题：是否有冗余配置可简化？

---

## 1. 审计范围与方法

- **非目标**：平台常量（`RECONNECT_DELAYS`、`MAX_MESSAGE_LENGTH`、`QUEUE_LIMIT`）——这些是环境适配参数，不是行为"超参数"
- **目标**：影响 Agent 策略行为的可调阈值和门控
- **方法**：每项回答 "能否用结构约束替代数字阈值？"

---

## 2. 被发现的行为参数

| # | 参数 | 位置 | 当前值 | 作用 | 可简化？ |
|---|------|------|--------|------|---------|
| 1 | `max_turns` | Agent loop | 90 | 硬限制 LLM 调用次数 | ⚠️ 必要，但可加自解释 |
| 2 | `degeneration_guard.loop_detection.repeat_threshold` | data/degeneration_guard.json | 3 | 同工具重复调用触发告警 | 🟡 可改为语义等价检测 |
| 3 | `degeneration_guard.info_density.window_size` | data/degeneration_guard.json | 4 | 信息密度检测窗口 | 🟡 可改为自适应窗口 |
| 4 | `degeneration_guard.info_density.new_elements_min` | data/degeneration_guard.json | 1 | 窗口内最少新元素数 | 🟡 和 #3 是同一概念的两个面 |
| 5 | `degeneration_guard.context_quality.retention_threshold` | data/degeneration_guard.json | 0.5 | 压缩后关键信息保留率 | ⚠️ 取决于任务类型，难统一 |
| 6 | `GDIResult.PUBLISH_THRESHOLD` | scripts | 70 | 胶囊质量最低分 | ⚠️ 业务决策，非技术参数 |
| 7 | `OPENCLAW_STRING_WARN_THRESHOLD` | env var | 60 | 字符串引用告警 | ⚠️ 安全审计参数 |
| 8 | `USE_HTML_OUTPUT` | gateway | True | HTML 输出开关 | ✅ 已简化——用户一键切换 |
| 9 | Context compressor params | agent/ | 多参数 | 压缩策略 | 🟡 见下文 |

---

## 3. LeWM 启发：从"调参数"到"结构约束"

### 3.1 LeWM 的核心洞察

```
Before (6 params):          After (1 param):
  - 预测损失权重              - λ (SIGReg 强度)
  - EMA 衰减率               
  - 辅助监督权重             ✅ 其他5个被结构消除：
  - 预训练编码器选择           SIGReg 强制潜变量高斯分布
  - 梯度裁剪阈值               → 坍塌在数学上不可行
  - 学习率调度               → 无需 EMA、辅助监督、预训练
```

### 3.2 MimirAether 中的等价机会

**不需要数字阈值的地方，用结构约束替代：**

| 当前做法 | LeWM 风格替代 |
|---------|-------------|
| `repeat_threshold: 3` — 计数器 | **语义等价检测**：不数调用次数，而是比较调用参数的语义向量。两次 `search(pattern="foo")` 和 `search(pattern="bar")` 不算重复，两次 `search(pattern="foo")` 才算 |
| `new_elements_min: 1` — 硬阈值 | **相对信息增益**：不要求"至少 1 个新元素"，而是检查 Fisher 信息矩阵的迹是否趋零（连续退化 == 无信息） |
| `retention_threshold: 0.5` — 硬数字 | **结构性保留**：关键实体（人名、项目名、决策）总是保留；非关键（中间计算）总是可丢弃。不用阈值，用实体分类 |

---

## 4. 简化建议

### P0: 立即可做（消除冗余）

| # | 内容 | 效果 |
|---|------|------|
| 4.1 | 合并 `window_size` + `new_elements_min` 为单参数 `info_density_ratio` | 两个参数测同一概念（信息密度），合二为一 |
| 4.2 | Context compressor 参数审计 | 检查是否有仅因历史原因保留的参数 |

### P1: 设计改进（不改变行为，提升清晰度）

| 4.3 | 将 `max_turns` 从硬数字变为 "任务预算"概念 | 简单任务自动低预算，复杂任务自动高预算 |
| 4.4 | `repeat_threshold` 改为语义等价检测 | 消除计数器，改为参数向量相似度 |

### P2: 结构变革（需改动逻辑，风险中等）

| 4.5 | `info_density` 改为自适应窗口 | 对话前期窗口更短（信息变化快），后期更长（趋于稳定） |
| 4.6 | `retention_threshold` 改为实体分类 | 不用数字，用 "关键实体字典" 决定保留 |

---

## 5. 结论

MimirAether 的参数已经相对精简。真正的 LeWM 式简化不是删数字，而是**把数字阈值改成结构性约束**。——这正是 degeneration_guard 和 context_compressor 的演进方向。

**优先级**：P0 两项（合并 window_size/new_elements_min + compressor 审计）可立即执行，风险最低。
