---
auto_load: false
name: mimiraether-context-compressor
description: MimirAether 上下文压缩：本仓库 agent/context_compressor 行为、MimirAetherAgent 参数、Gateway 卫生压缩与配置键（与运行时对齐）。
---

# MimirAether Context Compressor

## 描述

MimirAether 在对话过长时对上下文做**工具输出修剪**与**中间段 LLM/模板摘要**，以控制 token 并保留头尾关键消息。概念借鉴 Hermes；**实现与参数以本仓库代码为准**。

**设计来源（真源）**: 本仓库 [`agent/context_compressor.py`](agent/context_compressor.py)（`ContextCompressorV2`、`HermesStyleCompressor`）。Hermes 上游仅作背景，不替代本路径。

## 核心设计

### 分层保护策略

```
┌─────────────────────────────────────────────────────────────┐
│  HEAD           │  MIDDLE (Compressible) │  TAIL (Protected) │
│  Protected      │  LLM / template summary │  Token-oriented  │
│  ~3 messages    │  Structured summary     │  ~tail_token_budget│
└─────────────────────────────────────────────────────────────┘
```

- **HEAD**：前 `protect_first_n` 条消息（对齐边界时跳过孤立 tool 行），通常含系统与首轮交换。
- **MIDDLE**：`compress_start`～`compress_end` 之间，经 `_generate_summary`（LLM 失败则用模板摘要）。
- **TAIL**：按 `_find_tail_cut_by_tokens` 与 `tail_token_budget`（及 `protect_last_n` 等）保留尾部；**不是**「固定约 20K tokens」——见下文「运行时真源」。

### 两阶段（与 `ContextCompressorV2.compress` 一致）

1. **阶段 1 — 工具输出修剪**（无 LLM）
   - 旧 `role==tool` 且正文长度 **>** `_PRUNED_TOOL_MIN_CHARS`（**200**）的条目替换为占位符（见下表常量）。
2. **阶段 2 — 摘要与重组**
   - 对中间段调用 `_generate_summary`；摘要预算与 `_SUMMARY_RATIO`（20%）等相关；成功则插入一条摘要消息，否则插入简短占位说明。

## 运行时真源

### MimirAetherAgent 使用的压缩器

[`agent/core_loop.py`](agent/core_loop.py) 中构造（**2026-08-12 A1 变更后——本段已更新**）：

```text
MimirContextCompressor(
    model=model,
    context_length=int(self._context_length or 1048576),
    threshold_percent=_threshold_percent,  # 默认 0.50
    **_comp_policy,                        # decision_compressor_policy 附加参数
)
```

阈值优先级（core_loop.py L395-421）：**`MIMIR_COMPRESS_THRESHOLD` env > `get_tuned_float("compressor.threshold_percent")`（agent/tuned_thresholds.py）> 默认 0.50**。

⚠️ 压缩器类为 **`MimirContextCompressor(ContextCompressorV2)`**（agent/context_compressor.py:799），**已不是 HermesStyleCompressor**；`protect_first_n / protect_last_n / tail_token_budget` 不再由 core_loop 硬编码传入，改为 `compressor_init_kwargs_from_policy()`（agent/decision_compressor_policy.py:221）提供的 `_comp_policy`。`HermesStyleCompressor` 类仍存在（供 ACP/兼容路径），但 MimirAetherAgent 主循环用的是 MimirContextCompressor。

### ContextCompressorV2 类默认值（直接 `new` 实例时）

与 Agent 传入值不同处已标出。

| 字段 | 类 `__init__` 默认 | MimirAetherAgent 实际传入 |
|------|-------------------|---------------------------|
| `threshold_percent` | **0.50** | **0.50**（默认；`MIMIR_COMPRESS_THRESHOLD` env / tuned 可覆盖——2026-08-12 A1 后不再是 0.85） |
| `protect_first_n` | 3 | 3 |
| `protect_last_n` | **6** | **6** |
| `tail_token_budget` | `None`（则用 `threshold_tokens * summary_target_ratio` 动态算） | **4000** |
| `summary_target_ratio` | 0.20 | 0.20（未改，默认） |
| 初始 `context_length` | 8000 | 由 `core_loop` 在拿到 `model_metadata` 后调用 `compressor.update_model(...)` 覆盖 |

`update_model(model, context_length, ...)` 会重算 `threshold_tokens`、`max_summary_tokens`（见 [`context_compressor.py`](agent/context_compressor.py)）。`MimirAetherAgent` 在 `core_loop.__init__` 中在解析 `_context_length` 后调用 `self.compressor.update_model(...)`（失败时仅 debug 日志）。

### 自动触发：`needs_compression` vs `compress`

- [`needs_compression`](agent/context_compressor.py)：`last_prompt_tokens >= self.threshold_tokens`（来自 `ContextEngine` / `update_from_response` 设计）。
- [`ContextEngine.update_from_response`](agent/context_engine.py) 负责在每轮 API 返回后写入 `last_prompt_tokens`。
- **`core_loop.run_conversation`** 在每轮成功 `_call_model_with_tokens` 后调用 `_compressor_sync_usage_from_llm` → `self.compressor.update_from_response(...)`；`usage` 取自 API 返回（含流式末包），缺省时回退 `model_metadata.estimate_messages_tokens_rough(messages)`。**`compress()`** 内部仍会用 `_estimate_tokens(messages)` 等在**被调用时**做二次判断（见 `compress` 首段条件）。

### `compress()` 内顺序（真函数名）

见 [`ContextCompressorV2.compress`](agent/context_compressor.py)：估算 `display_tokens` → 未达阈值或消息过少则原样返回 → `_prune_old_tool_results` → `_align_boundary_forward` / `_find_tail_cut_by_tokens` → `_generate_summary` → 组装消息 → `_sanitize_tool_pairs`。

### 常量速查（`agent/context_compressor.py`）

| 符号 | 值 / 行为 |
|------|-----------|
| `_PRUNED_TOOL_PLACEHOLDER` | `[Old tool output cleared to save context space]`（**不是**简短版 `[Old tool output cleared]`） |
| `_PRUNED_TOOL_MIN_CHARS` | 200（超过才修剪） |
| `_SUMMARY_RATIO` | 0.20 |
| `_SUMMARY_FAILURE_COOLDOWN` | 600 秒（**10 分钟**）摘要失败冷却 |
| `_MINIMUM_CONTEXT_LENGTH` | `update_model` 时 `threshold_tokens` 下限相关 |
| `SUMMARY_PREFIX` | `[CONTEXT COMPACTION — REFERENCE ONLY]` |

## Gateway 与会话卫生（与 Agent 内压缩分离）

[`gateway/run.py`](gateway/run.py) 在 transcript 过长时可在 **Agent 跑起来之前**做「卫生」压缩（注释说明与 Agent 内压缩分工不同）。

- 从 **`_hermes_home / "config.yaml"`** 读配置（与仓库内示例 [`config.yaml`](config.yaml) **未必是同一文件**）。
- **`compression.enabled`**：仅此布尔（及 truthy 字符串）控制是否启用卫生压缩；路径见代码中 `_hyg_data.get("compression", {})`。
- **卫生触发阈值（2026-08-02 P0 修复后）**：`agent_route_mixin.py` L322 `_compress_token_threshold = 200_000` **固定值**（替代旧的 `context_length × 0.85` = 850K）。token 来源**仅用 actual**（`session_entry.last_prompt_tokens`），`estimated` 不再触发——旧估算偏差 3.05×（10:31 estimated 244,759 vs 10:34 actual 80,359）导致"该压不压"。消息数 ≥400 硬阀保留兜底。
- 优先使用 `session_entry.last_prompt_tokens`，否则用 `estimate_messages_tokens_rough(history)`。

## ⚠️ P0 coroutine bug 教训（2026-08-02 修复）

**症状**：gateway.log 连续 70 天（841 次触发 0 次成功）报 `auto-compress failed: cannot unpack non-iterable coroutine object`。

**根因链**（三层叠加）：
1. `agent/context_compressor.py:524` `compress` 是 **`async def`**（内部 L566 `await _generate_summary`）
2. `run_agent.py:160` `AIAgent._compress_context`（sync def）调 `comp.compress(...)` **无 await** → 返回 coroutine 对象
3. `agent_route_mixin.py:399` 把 `_compress_context` 丢进 `run_in_executor` 线程池 → lambda 返回 coroutine → `_compressed, _ = <coroutine>` → TypeError → L441 except 吞掉

**修复模式**（async 链必须全链路 await，禁止在 sync→async 边界丢 run_in_executor 包装）：
- `run_agent.py:145` → `async def _compress_context` + L160 `return await comp.compress(...)`
- `agent_route_mixin.py:398`（session hygiene）/ `command_handlers.py:1397`（/compress）/ `tuning_commands_mixin.py:383` → 去 `run_in_executor` 包装，直接 `await`
- `acp_adapter/server.py:650`（sync `_cmd_compact`）→ `agent.async_bridge.run_async` 桥接

**排查信号**：`grep "auto-compress failed" gateway.log | wc -l` 若 >0 且含 "coroutine object"，先查是否 `async def` 被 sync 调用且无 await，再查是否被 run_in_executor 包装。修复顺序：先 coroutine 后触发器，不能反。

## 配置键 → 代码位置（摘要）

| 配置 / 行为 | 读取位置 | 说明 |
|-------------|----------|------|
| `compression.enabled` | `gateway/run.py`（`_hermes_home` 下 `config.yaml`） | 仅 **session hygiene** |
| 卫生 85% 阈值 | 同上，常量 | 非配置项 |
| `model` / `context_length` / `provider` / `base_url` | 同上 | 用于解析上下文长度与运行时；**不**自动驱动 `ContextCompressorV2.update_model` |
| Agent `threshold_percent` | `agent/core_loop.py` L397-421 | 默认 0.50，env `MIMIR_COMPRESS_THRESHOLD` > `get_tuned_float("compressor.threshold_percent")` > 默认（A1 变更后非硬编码 0.85） |
| Agent `_comp_policy`（protect/tail 等） | `agent/decision_compressor_policy.py` L221 `compressor_init_kwargs_from_policy()` | 策略提供，非硬编码 |

## 结构化摘要模板

下面模板适合**人类撰写**技能文档或与用户对齐期望。

运行时 LLM 摘要使用的节标题见 [`_call_summary_llm`](agent/context_compressor.py) 内嵌 prompt（如 `Pending Asks` 等），与下表**用词可能略有不同**；以代码内模板为生成真源。

```markdown
## Goal
[What the user is trying to accomplish]

## Constraints & Preferences
[User preferences, coding style, constraints]

## Progress
### Done
[Completed work with specific file paths, commands, results]
### In Progress
[Work currently underway]
### Blocked
[Any blockers or issues]

## Key Decisions
[Important technical decisions and why]

## Resolved Questions
[Questions already answered - include answers]

## Pending User Asks
[Unanswered questions/requests - "None." if none]

## Relevant Files
[Files read, modified, created]

## Remaining Work
[What remains - framed as context, not instructions]

## Critical Context
[Specific values, errors, configs]

## Tools & Patterns
[Tools used and effective patterns]
```

## 失败与降级

- 摘要失败：冷却 **`_SUMMARY_FAILURE_COOLDOWN`**（10 分钟）内 `_generate_summary` 早退；可用模板摘要分支。
- `compress` 在无法满足头尾边界时可能**不压缩**并返回原消息（见 `compress_start >= compress_end` 分支）。

## 使用场景

1. **Gateway 卫生压缩**：长会话、大 transcript，受 `compression.enabled` 与 85% 常量阈值约束（见上）。
2. **Agent 循环内**：设计上在 `needs_compression` 为真后调用 `compress`；`last_prompt_tokens` 由每轮 `update_from_response` 更新（见上）。
3. **手动 `/compress`**：`gateway/run.py` 中 `_handle_compress_command` 依赖 `run_agent.AIAgent` 的 `context_compressor` 与 `_compress_context`；`run_agent.AIAgent` 委托至 `MimirAetherAgent.compressor.compress(...)`。

## 已知限制（文档范围外修复）

- 无 API `usage` 且粗估失败时，`last_prompt_tokens` 可能仍为 0，自动触发仍可能偏保守。
- Gateway 卫生压缩仍使用独立配置与 85% 常量阈值，与 Agent 内 `threshold_percent` 等**不一定**数值一致。

## ⚠️ Pitfall: 卫生压缩日志 "token 翻倍" 是口径假象（2026-08-02 定位）

日志 `Session hygiene: compressed 1923 → 1922 msgs, ~112,035 → ~225,789 tokens` 中 **112K→225K 不是上下文真变大**，是**两个不可比的数字**放进一个箭头：

1. **压缩前** `_approx_tokens = session_entry.last_prompt_tokens`（`agent_route_mixin.py` L332）= **API 实际 prompt_tokens**（tokenizer 精确计数）。
2. **压缩后** `_new_tokens = estimate_messages_tokens_rough(_compressed)`（L409）= `(sum(len(str(msg)))+3)//4`（`model_metadata.py` L961）**字符粗估**，对代码/JSON/中文消息系统性高估 ~2x（注释自认 overestimates 30-50%）。
3. 1923→1922 只少 1 条 = `_hyg_msgs` 只保留 user/assistant（L370-375）过滤掉 tool 消息；`_compress_context(approx_tokens=112035)` → `compressor.compress(current_tokens=112035)` **未达 threshold（0.85×ctx ≈170K）→ no-op 原样返回**，但日志谎报 "compressed"。
4. 触发原因不是 112K≥200K，而是 **`_msg_count=1923 ≥ 400` 硬消息数阀**（L344-347）——对"条数多但每条小"的中文短消息会话误触发。

**判断要点**：看到 hygiene 日志 token 翻倍先查**口径是否一致**，再查 **compress 是否真的 no-op**（消息数几乎不变 = 未达阈值）。

## 🧠 V-JEPA 2.1 Layer 1 自检 (Session 75+)

**来源**: `docs/MEMORY_SELF_CHECK.md` — 压缩后实体保留率自检

每次 `compress()` 后检查:
```
1. 实体保留率: 压缩摘要中是否保留了原始 HEAD 中的关键实体?
   - 关键实体: 文件名 / 工具名 / 决策关键词 / 约束条件
   - 阈值: ≥80% 实体可回溯 → 压缩质量 OK
   - <80% → 增加 HEAD 保留或提高 tail_token_budget

2. 压缩频率: 是否过频压缩?
   - 阈值: ≤1次/3轮
   - 过频 → 提高 threshold_percent (当前 0.85)
```

---

_概念溯源: Hermes Agent context compressor；实现真源: 本仓库 `agent/context_compressor.py` v2.3 / `HermesStyleCompressor`_

## 📋 复活与审计追踪（2026-08-09 追加）

### 复活记录
- **日期/操作**：2026-08-09 · Mimir 执行（刘哥确认"按你的建议来"）
- **复活原因**：2026-08-06 A5+A7 归档（commit a75eec3，display.py 等大文件归档）时**随大流误入 dormant**——无独立评估"该废弃"。内容仍为**正在运行的机制**（Gateway 卫生压缩每日执行）的排障手册，8/2 的 P0 coroutine bug 修复模式 + token 翻倍口径假象教训均沉淀于此，实战价值有效。
- **移动路径**：`skills/.dormant/mimiraether/mimiraether-context-compressor/` → `skills/mimiraether/mimiraether-context-compressor/`（repo + home 两侧同步，dormant 无残留）

### 工作状态（当前）
- **类型**：文档型排障技能（非执行型）——不主动跑，需要时 skill_view 加载
- **auto_load**：false（懒加载，平时不占上下文——这是 7 月 c6726eb 懒加载改造的既定设计，非异常）
- **使用场景**：① Gateway 卫生压缩日志异常 ② token 翻倍/压缩失败排查 ③ 压缩器参数核对
- **版本**：SKILL.md 12,470B（8/2 12:46 最后更新，含 P0 教训）

### 审计要点（以后判断它是否运行/有 bug/需迭代）
| 检查项 | 方法 | 健康信号 |
|--------|------|---------|
| 压缩器是否在运行 | `grep "auto-compress failed" ~/.mimiraether/logs/gateway.log \| wc -l` | =0（有则先查 coroutine 链） |
| 压缩是否真生效 | gateway.log `Session hygiene: compressed` 前后消息数/token 口径 | 消息数大幅下降；token 用同口径比（勿被"翻倍"误导） |
| 参数与代码是否一致 | 对比本技能"运行时真源" vs `agent/context_compressor.py` / `agent/core_loop.py` 实参 | 2026-08-17 实测：gateway 卫生触发=固定 200K actual（agent_route_mixin.py L322，非 85%×ctx，85% 仅日志残留文案 bug）；agent 内 threshold_tokens=1M×0.35=350K（tuned_thresholds.json `compressor.threshold_percent: 0.35`，core_loop L397-421 env>tuned>0.50）；tail=4000 |
| 是否需要迭代 | 技能内知识是否落后于代码（代码改版后本技能未同步） | 若代码变动而本技能未更新 → 需迭代 |

_审计记录：每次使用/检查后在此节下方追加一行（日期 + 检查项 + 结果），形成审计轨迹。_

| 日期 | 检查项 | 结果 |
|------|--------|------|
| 2026-08-23 | 压缩器运行健康 | `auto-compress failed` 计数=0（无 P0 coroutine 复发）；无近期 hygiene 事件（26K tokens 远未达 200K 实际阀） |
| 2026-08-23 | 参数与代码一致 | 实测 threshold_tokens=350K（tuned 0.35×1M，core_loop env>tuned>0.50 链路），与 2026-08-17 记录一致 ✓ |
| 2026-08-23 | 上下文占用 | prompt 26,096 / 阈值 350,000（7.5%），无需压缩 |
| 2026-08-23 | 压缩器运行健康（复核） | `auto-compress failed` 计数=0（grep -c 实测）✓；无近期 hygiene 事件（26.5K tokens 远未达 200K 实际阀）✓ |
| 2026-08-23 | 参数与代码一致（复核） | context_usage 实测 threshold_tokens=350,000（0.35×1M）✓；tuned 数据文件真实路径=`~/.mimiraether/data/tuned_thresholds.json`（不在 repo 内），`compressor.threshold_percent: 0.35` 盘上确认 ✓ |
| 2026-08-23 | 上下文占用（复核） | prompt 26,486 / 阈值 350,000（7.6%），无需压缩 |
| 2026-08-23 | 复核（Buzz 消息再触发） | ① `grep -c "auto-compress failed"` =0 ✓ ② gateway.log 无新 "Session hygiene" 记录 ✓（26K tokens 远未达 200K 实际阀）③ context_usage 实测 prompt=26,381 / threshold=350,000（7.5%）✓ ④ tuned_thresholds.json `compressor.threshold_percent: 0.35` 盘上复核 ✓（~/.mimiraether/data/tuned_thresholds.json:4，tune_audit.jsonl 显示 0.45→0.40→0.35 调参链）· 结论：压缩器健康、参数与代码对齐，无迭代需求 |
- 2026-08-23 · Mimir 执行（Buzz 消息触发 skill 加载）· ① `grep -c "auto-compress failed"` = 0 ✅（P0 coroutine 无复发）② `grep -c "coroutine object"` = 0 ✅ ③ context_usage 实测 prompt=25,709 / threshold=350,000（= 1M×0.35，与 tuned_thresholds `compressor.threshold_percent: 0.35` 及本技能文档一致）✅ ④ 当前 gateway.log 无 "Session hygiene" 记录（本轮未触发卫生压缩/日志已轮转）· 结果：压缩器健康，参数与代码对齐，无迭代需求。
- 2026-08-23 · 技能路由 NUDGE 加载 + 健康检查（证据：gateway.log 共 9348 行）：`grep -c "auto-compress failed"` = **0**（无 coroutine P0 复发）；`grep -c "coroutine object"` = **0**；compress/hygiene 相关命中 18 处，最近一次真实卫生压缩为 **L5173-5174（2026-08-15）**：`Session hygiene: compressed 162 → 162 msgs, ~200,280 → ~35,314 tokens`——口径一致（actual→粗估虽不同但方向为降）、真实生效非 no-op；8-15 后无新 hygiene 触发（上下文未达 200K actual / 400 条硬阀，属正常）。压缩器运行健康。
- 2026-08-23 · Buzz 消息协议触发加载 + 复核：`grep -a -c "auto-compress failed"` = **0** ✓；`grep -a -c "coroutine object"` = **0** ✓（gateway.log 含二进制字节，需 `grep -a` 文本模式）；最近 hygiene 事件仍为 **2026-08-15**（162→162 msgs, ~200,280→~35,314 tokens，真实生效非 no-op）；context_usage 实测 prompt=27,054 / threshold=350,000（7.7%）——远未达 200K actual 卫生阀。结论：压缩器健康、参数与代码对齐，无迭代需求。
- 2026-08-23 · Buzz 消息（空任务载荷）+ 技能路由 NUDGE 再加载 · `grep -c "auto-compress failed"` = **0** ✅、`grep -c "coroutine object"` = **0** ✅、`Session hygiene` = 2（均为历史记录，无新触发）✅ · context_usage 实测 prompt=26,946 / threshold=350,000（7.7%，远未达阀）✅ · 结果：压缩器健康，参数与代码对齐（0.35×1M），无迭代需求。
- 2026-08-23 · 技能路由 NUDGE 再加载 + 健康检查（证据：gateway.log 共 9350 行）：`grep -c "auto-compress failed"` = **0** ✅；`grep -c "coroutine object"` = **0** ✅；`grep -c "Session hygiene"` = **2**（最新真实卫生压缩仍为 2026-08-15 那次，无新增异常触发）；context_usage 实测 prompt=**27,563** / threshold=**350,000**（7.9%，无需压缩）✅。结论：压缩器运行健康、参数与代码对齐（0.35×1M 链路），无迭代需求。
- 2026-08-23 · Buzz 消息 NUDGE 再加载（gateway.log 9350 行，含二进制需 `grep -a`）：`auto-compress failed` = **0** ✓；`coroutine object` = **0** ✓；最后一次真实卫生压缩仍为 **L5173-5174（2026-08-15）**（162→162 msgs, ~200,280→~35,314 tokens，真实生效），此后无新触发；context_usage 实测 prompt=26,536 / threshold=350,000（= 1M×0.35 tuned，7.6%）✓——压缩器健康、参数对齐、无迭代需求。
- 2026-08-23 · 技能路由 NUDGE 再次加载 + 复核（gateway.log 需 `grep -a` 取证，二进制）：`grep -ac "auto-compress failed"` = **0** ✓；`grep -ac "coroutine object"` = **0** ✓；最近 hygiene 事件仍为 L5173-5174（2026-08-15，200,280→35,314 tokens 真实生效），之后无新触发 ✓；context_usage 实测 prompt=26,772 / threshold=350,000（7.6%），远未达 200K actual 卫生阀与 400 条硬阀 ✓。结论：压缩器健康，参数与代码对齐，无迭代需求。
- 2026-08-23 · Buzz 消息触发 NUDGE 再加载 + 复核（gateway.log 共 9350 行）：`grep -c "auto-compress failed"` = **0** ✓；`grep -c "coroutine object"` = **0** ✓；`grep -c "Session hygiene"` = 2（最近一次真实压缩 2026-08-15 L5173-5174，之后无新触发，上下文远未达 200K actual 阀）✓。结论：压缩器健康、参数与代码对齐，无迭代需求。
- 2026-08-23 · 技能路由 NUDGE 加载 + 健康检查（Buzz 消息触发）：`grep -c "auto-compress failed"` = **0** ✅（无 coroutine P0 复发）；`grep -c "coroutine object"` = **0** ✅；最近真实卫生压缩仍为 **L5173-5174（2026-08-15）**：162 → 162 msgs, ~200,280 → ~35,314 tokens（口径一致、真实生效）；context_usage 实测 prompt=26,774 / threshold=350,000（7.6%，远未达 200K actual 阀）✅ · 结论：压缩器健康、参数与代码对齐，无迭代需求。
- 2026-08-23 · 技能路由 NUDGE 加载 + 健康检查（本轮，verify-before-report 触发后重取证）：gateway.log 共 **9350** 行；`grep -c "auto-compress failed"` = **0** ✅（P0 coroutine 无复发）；`grep -c "coroutine object"` = **0** ✅；最近真实卫生压缩仍为 **L5173-5174（2026-08-15）** `compressed 162 → 162 msgs, ~200,280 → ~35,314 tokens`（8-15 后无新触发，正常）；`tuned_thresholds.json` 盘上确认 `compressor.threshold_percent: 0.35` ✅；context_usage 实测 prompt=26,772 / threshold=350,000（7.6%），无需压缩 ✅。结论：压缩器健康、参数与代码对齐、无迭代需求。注：gateway.log 含二进制字符，grep 需 `-a` 文本模式（2026-08-23 实测）。
- 2026-08-23 · Buzz 消息 NUDGE 再触发 + 健康检查：`grep -c "auto-compress failed"` = **0** ✅；`grep -c "coroutine object"` = **0** ✅；context_usage 实测 prompt=27,016 / threshold=350,000（7.7%，远未达 200K 实际卫生阀）✅。结论：压缩器健康、参数与代码对齐、无迭代需求。
- 2026-08-23 · Mimir（verify-before-report 触发后重取证追加）：gateway.log 共 **9350** 行（含二进制字符，grep 须 `-a`）；`grep -a -c "auto-compress failed"` = **0** ✅（P0 coroutine 无复发）；`grep -a -c "coroutine object"` = **0** ✅；最近真实卫生压缩 **L5173-5174（2026-08-15）** `compressed 162 → 162 msgs, ~200,280 → ~35,314 tokens`——actual→粗估同向下降、真实生效非 no-op ✅；`tuned_thresholds.json` 盘上确认 `compressor.threshold_percent: 0.35` ✅（~/.mimiraether/data/tuned_thresholds.json:4）；context_usage 实测 prompt=27,027 / threshold=350,000（7.7%），无需压缩 ✅。结论：压缩器健康、参数与代码对齐、无迭代需求。
- 2026-08-23 · Buzz 消息（Hermes）技能路由 NUDGE 再触发 + 健康检查（`grep -a` 文本模式）：`grep -a -c "auto-compress failed"` = **0** ✅（P0 coroutine 无复发）；`grep -a -c "coroutine object"` = **0** ✅；Session hygiene 命中 2 条（仍为 8-15 L5173-5174 真实压缩 162→162 msgs / ~200,280→~35,314 tokens，无新触发）；`tuned_thresholds.json` 盘上确认 `compressor.threshold_percent: 0.35` ✅；context_usage 实测 prompt=29,351 / threshold=350,000（8.4%），无需压缩 ✅。结论：压缩器健康、参数与代码对齐、无迭代需求。
- 2026-08-23 · Buzz 消息（Hermes，协议模板无任务载荷）NUDGE 加载 + 健康检查：`grep -a -c "auto-compress failed"` = **0** ✅；`grep -a -c "coroutine object"` = **0** ✅；Session hygiene 命中 2 条（仍为 8-15 L5173-5174 历史真实压缩，无新触发）✅；context_usage 实测 prompt=29,056 / threshold=350,000（8.3%），无需压缩 ✅。结论：压缩器健康、参数与代码对齐、无迭代需求。注：本条操作中曾误将 home 侧损坏文件（16 行，含 read_file handle 垃圾行）cp 覆盖 repo 侧完整版（262 行），已 git restore 恢复并重新追加；home 侧随后以 repo 完整版同步修复。
- 2026-08-23 · Buzz 消息（Hermes，协议模板无任务载荷）NUDGE 再加载 + 健康检查（gateway.log 共 9353 行，`grep -a` 文本模式）：`grep -a -c "auto-compress failed"` = **0** ✅（P0 coroutine 无复发）；`grep -a -c "coroutine object"` = **0** ✅；Session hygiene 命中 2 条（仍为 8-15 L5173-5174 历史真实压缩 162→162 msgs / ~200,280→~35,314 tokens，无新触发）✅；context_usage 实测 prompt=28,814 / threshold=350,000（8.2%），远未达 200K actual 卫生阀与 400 条硬阀 ✅。结论：压缩器健康、参数与代码对齐、无迭代需求。
