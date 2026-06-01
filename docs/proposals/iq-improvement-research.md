# IQ 提升调研：四个方向 + 两个待探索

> **作者**：Mimir（2026-06-01）
> **目的**：为 Cursor 风险评估和可行性判断提供完整输入
> **当前 rubric**：4.9/10（目标 5.5+）

---

## 方向 A：先搜再答肌肉记忆

### 现状
- `session_search` 功能可用，但 **不是第一反应**
- 用户问历史类问题（"xx 做了么""确认一下""之前"）→ 我先答再搜，有时答错
- 不是代码能力问题，是 **行为习惯问题**

### 做法
不改 Python 代码。在 `agent/prompt_builder.py` 的 `IQ_EVOLUTION_DIRECTION_GUIDANCE`（或 cross-session-context）中加一条硬规则：

```
历史/确认/检查类问题：在回答正文之前，必须先用 session_search。
```

### 代码改动
**零行**（纯 prompt 配置改动）

### 风险
- 🟢 低 —— prompt 加规则不影响现有逻辑
- 🟢 可逆 —— 改回去只需删一行

### 收益预估
IQ rubric I1（跨会话回忆）从 5.0 → 6.5，整体 +0.3

---

## 方向 B：世界模型启用

### 现状
Phase 0 + Phase 1.1 代码全部合并，tier0 665 PASS。但 **所有 WM 功能 env 门控默认关**：

| 变量 | 当前值 | 功能 |
|------|:------:|------|
| `MIMIR_WM_VOE_LEARNING` | 0 | surprise 事件写入 JSONL + learned_surprises |
| `MIMIR_WM_VOE_RECALL` | 0 | 同场景第二次不 surprise |
| `MIMIR_WM_VOE_REPLAN_CTX` | 0 | 学习上下文注入 replan |
| `MIMIR_WM_PREDICTOR` | 0 | 规则预测器接 agent_loop |

两个模块已合并但完全沉默：
- `agent/world_model_spike.py` — 规则级预测器
- `agent/wm_voe_learning.py` — VoE 检测 + 学习持久化

### 做法（分级）
| 步骤 | 操作 | 风险 | 改动 |
|:----:|------|:----:|:----:|
| **B1** | `MIMIR_WM_VOE_LEARNING=1` | 🟢 | 零改动 |
| **B2** | `MIMIR_WM_VOE_RECALL=1`（依赖 B1 跑 3 天） | 🟢 | 零改动 |
| **B3** | `MIMIR_WM_VOE_REPLAN_CTX=1` | 🟡 | 零改动 |
| **B4** | 预测器接 `agent_loop`（~20 行） | 🟡 | 小改动 |
| **B5** | LLM 预测器（新模块） | 🔴 | 新开发 |

### 风险
- B1-B3：🟢 零改动，纯 env 开关，**随时可关**
- B4：🟡 需确定 agent_loop 的 hook 点（`core_loop.py` 的迭代间），tier0 验证可保回归
- B5：🔴 新模块，需刘哥拍板 scope

### 收益预估
I3（学习能力）3.5 → 4.5，整体 +0.15

---

## 方向 C：AUTO_EVOLVE 默认开

### 现状
`MIMIR_AUTO_EVOLVE=0`（默认关）。Gate C 代码（analysis→evolution 全链路）全部合并，但 **默认不触发**。
- 进化链只在 Cursor 跑工程任务时被动触发
- 日常对话从不自省
- `post_close_analysis` + `skill_evolution` 代码就位，只缺一个 env 默认值

### 做法
将 `agent/constants.py`（或相关 env 配置）中 `MIMIR_AUTO_EVOLVE` 默认值从 `0` 改为 `1`。

### 代码改动
**1 行**（默认值常量）

### 风险
- 🟡 中 —— 日常对话每轮结束后会多一次 LLM 调用（`post_analysis` 分析 + 可能的 `skill_evolution` 修改）
- 可能增加成本：按 1 次分析/会话 ≈ 500 tokens，日均 10 会话 ≈ 5000 tokens/天
- 🟢 可观察：evolution eval 周常自动记录 ok%，可及时发现退化
- 🟢 可逆：改回 0 即可

### 收益预估
I3（学习能力）3.5 → 5.0，整体 +0.2

---

## 方向 D：IntentPredictor（上限最高）

### 现状
Mimir 当前的"意图判断" = `world_model_spike.py` 中的 **几十行正则匹配**。搜关键词（"历史""之前""检查"）猜用户意图。

pi-agent 不是这样做的。pi 有真正的 intent 抽象层（任务分解 → 策略选择 → 工具路由）。

### 做法
新模块 `agent/intent_predictor.py`，在 turn 0（LLM 调用前）预测：
1. **意图类别**：查历史 / 执行任务 / 闲聊 / 评估
2. **复杂度**：简单（单工具） / 中等 / 复杂（多轮）
3. **策略建议**：要不要先搜 / 用什么 model provider / 什么工具集

已有基础代码可复用：
- `world_model_spike.py` 中的规则预测器
- `intent_action_guard.py` 中的动作防护
- `context_compressor.py` 中的上下文分析

### 代码改动
新文件 ~200 行 + `core_loop.py` 加 ~10 行 hook

### 风险
- 🔴 **核心风险**：如果 IntentPredictor 预测错误，可能误导整个 agent 行为（如把搜索问题当执行任务）
- 需要 fallback 机制：预测置信度低于阈值时走默认路径
- 需要刘哥拍板 scope（Phase 1.2 还是 Phase 2）

### 收益预估
I2（意图与模型）1.0 → 5.0，整体 +0.5

---

## 方向 E：对话内 nudge（待调研）

### 现状
Hermes 在 agent loop 中有定时 nudge 机制（`_memory_nudge_interval` / `_skill_nudge_interval`）——每 N 轮对话后，自动检查上下文是否有值得写入 memory/skill 的信息。

Mimir 只在任务结束后的 `post_close_analysis` 中做一次分析，对话中间错过大量可记忆信息。

### 待评估
- 改 `core_loop.py` 加 nudge 定时器（每 3-5 轮一次）
- 调用现有的 `monitor_collector.py` 做信息提取
- 调用 `memory()` 或 `skill_manage(create)` 写入
- 需确定 nudge 不干扰主对话流（异步或低优先级）

---

## 方向 F：并行工具执行（待调研）

### 现状
Mimir 固定串行——一次一个 tool call，循环直到无 tool call。
pi-agent 支持 `ToolExecutionMode.parallel`——多个独立工具可同时执行。

### 待评估
- 识别"独立"工具（如 `read_file` 不依赖 `web_search`）
- 改 `execution_pipeline.py` 支持并发执行
- 收益：复杂任务减少 30-50% 延迟
- 风险：并发写同一个文件等竞态条件

---

## 总结优先级（Mimir 建议）

| 优先级 | 方向 | 风险 | 改动量 | IQ 收益 | 依赖 |
|:------:|:----:|:----:|:------:|:-------:|:----:|
| P0 | A: 先搜再答肌肉记忆 | 🟢 | 0 行 | +0.3 | 无 |
| P0 | B1-B2: 世界模型开门 | 🟢 | 0 行 | +0.15 | 刘哥拍板 |
| P0 | C: AUTO_EVOLVE 默认开 | 🟡 | 1 行 | +0.2 | 刘哥拍板 |
| P1 | D: IntentPredictor | 🔴 | ~210 行 | +0.5 | 刘哥批 scope |
| P2 | E: 对话内 nudge | 🟡 | ~50 行 | ? | 需设计 |
| P2 | F: 并行工具 | 🟡 | ~100 行 | ? | 需设计 |
