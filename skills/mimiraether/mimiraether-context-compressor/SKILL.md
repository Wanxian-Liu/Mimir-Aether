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

**B9 一等公民上限（2026-09-13 · commit `41fd67c`）**：`resolve_threshold_tokens()` 在 percent/env 解析之后追加一层夹紧 —— `threshold = min(configured, tuned "compressor.effective_window_tokens", floor(0.75 × context_length))`。**tuned 键缺失 ⇒ 该层完全不生效**（严格向后兼容）。当前（**2026-09-22 全身体检实测更新 · 原文已过期**）真源 = **`~/.mimiraether/data/tuned_thresholds.json`**（**不在仓内 `data/`**——仓内无此文件，按仓路径读会得到 `FileNotFoundError` 而误判"tuned 键缺失⇒夹紧层不生效"）；其 `overrides` = `threshold_percent 0.35` + `effective_window_tokens 300000` + `hygiene_token_threshold 300000`，且 `~/.mimiraether/.env` 的 `MIMIR_COMPRESS_THRESHOLD_TOKENS=300000`（**sha256 指纹判定**：len=38、sha12 命中候选 `300000`；不要看截图，含 `TOKEN` 的值会被脱敏成 `***`）⇒ 目标阈值 **300,000**（历史：350,000 → 120,000 → 300,000）。
**运行时健康告警（2026-09-22）**：`~/.mimiraether/data/compression_quality.jsonl` 末行 = **`2026-09-17T11:38:55`**（537 行 = 458 rollback / 78 applied）⇒ 该层**近 5 天零事件 = "未触发"，≠ 健康**；要证明它活着必须做**触发式验收**（钉 5K 跑一次再还原 300K）。另 hygiene **==** agent **== 300000** ⇒ 等值零余量，仍属"假绿族"风险区（hygiene < agent 时会结构性空转却记 `applied`）。`source` 只追加不重写（`+cap:effective_window_tokens` / `+cap:window_ratio`），夹紧取胜时打 `[COMPRESS-CAP]` INFO。
**生效与验收（易误判）**：compressor 只在 `__init__` 读一次 ⇒ **「代码已提交」≠「已生效」**；判据 = `MainPID` 启动时刻 **>** commit 时刻，且 `[COMPRESS-INIT]` 出 `threshold_tokens=120000` 且 source 含 `+cap:`。反例实证（2026-09-13 07:17）：`last_context_usage.json` 仍写 `threshold_tokens=350000`、无 `caliber` 字段 ⇒ 旧代码在跑（PID 222449 启动 06:03:40 < commit 07:15:52）。
**B10 遥测口径（同 commit）**：payload 增 `pid` / `writer_kind` / `caliber`（`<model>@<ctx>/thr=<thr>`）；`writer_kind=aux` 在 TTL 1800s 内不得覆盖 main，改写 `last_context_usage_aux.json`；读端 `mimir_ops context_usage` 标 `caliber_annotation`（真源）+ aux 块（旁路）。

**绝对阈值通路（2026-09-13 实测补充——此前本节只记了百分比 env，属文档缺口）**：`agent/context_compressor.py` 另有一条 **`MIMIR_COMPRESS_THRESHOLD_TOKENS`**（模块常量 `_COMPRESS_THRESHOLD_TOKENS_ENV`，L47；解析函数 `resolve_threshold_tokens()` L79），在 compressor **`__init__` 时直接覆盖 `threshold_tokens`（绝对值，优先级高于 percent×context_length）**。实测（`.venv/bin/python3` 断言）：`=5000` → `resolved_tokens=5000` / `source=env:MIMIR_COMPRESS_THRESHOLD_TOKENS`；`=abc` → 记 WARNING 并降级回 percent（350,000），不抛。**用途**：把阈值临时钉到 5K 即可**必然触发一次真压缩**（无需等自然越线）——即四方卡 Q7 的构造法，验收后须还原 350K。

⚠️ **2026-09-13 实测补充（钉阈值式验收必读）**：上述「一键钉死」**只对 shell / 进程内注入有效；对 systemd drop-in 无效**。盘上实证（批 2 B4-b v1/v2 两窗口连续 FAIL 的真因）：drop-in `mimiraether.service.d/b4b-threshold.conf` 写了 `Environment=<KEY>=5000` 且 `systemctl show -p Environment` 也显示带 key，但**阈值始终 350000** —— 因为该键被**两层** `.env` 压掉：① **systemd 层**：单元 `EnvironmentFile=-~/.mimiraether/.env` 的赋值**优先于** `Environment=`，`/proc/<pid>/environ` 实测该键**只有一条**（值来自 `.env`，drop-in 的值根本没进进程）；② **应用层**：`gateway/run.py:88 load_hermes_dotenv` → `mimir_cli/env_loader.py:100 _load_dotenv_with_fallback(user_env, override=True)` 用 python-dotenv **再次覆盖**。⇒ **凡「env 注入式验收」必须先证明目标键在 dotenv 之后仍存活**：对账两处 = `dotenv_values(~/.mimiraether/.env)[KEY]` 与 `/proc/<gateway pid>/environ`（后者若仍是 `.env` 的值，则 drop-in 无效）；`[COMPRESS-INIT] source=` 字段可交叉验证（`env:<KEY>` 才是真生效）。另注：`.env` 里的**行内注释会被 systemd `EnvironmentFile=` 吞进值**（`KEY=350000  # was 80000` → 值非法，实测 `int()` 失败），只是常被 dotenv 清洗 + 数值巧合掩盖 —— 别把这种巧合当「生效」。

⚠️ **注记 2（2026-09-13 F1 实测 · 更危险的显示层陷阱）**：**键名含 `TOKEN`/`KEY`/`SECRET` 的行，其值会被工具输出层脱敏成 `***`** ——
`.env` 里 `MIMIR_COMPRESS_THRESHOLD_TOKENS=120000` 在 `read_file`/`search_files`/部分 `execute_code` 打印中**显示为 `=***`**，
极易被误判为「`.env` 又被 write_file 覆盖成占位符」（与 `DEEPSEEK_API_KEY=***` 那次误诊同型）。
**判据（唯一可靠）**：不要凭输出截图定性；在 Python 里对**磁盘原文**做 **sha256 断言**——
`hashlib.sha256(line.encode()).hexdigest()` 与候选串（`[...]=120000` / `[...]=350000` / `[...]=***`）逐一比对，命中即真值；
或比对 `/proc/<gateway pid>/environ`。**本文件已知真值（2026-09-13 实测）**：`.env` 的 `MIMIR_COMPRESS_THRESHOLD_TOKENS=120000`（hash 命中候选 120000）。
**2026-09-14 RS16 补充（同一陷阱的更强形态）**：脱敏**对空串也生效** —— `{"api_key": ""}` 在工具输出里同样显示成 `***`，**空串与真值完全不可区分**（RS16 第一版探针据此误判「gateway 层有 key」，后被受控差分推翻）。⇒ 探针字段名必须**避开** `key`/`token`/`secret`，只输出 `len` + `sha8` 指纹。

⚠️ **注记（易误判）**：`read_file`/`grep` 的输出层会把该长大写常量**折叠显示**为 `"MIMIR_...KENS"`，看起来像文件里的字符串写坏了——**是显示层假象，非文件内容**。判据必须用运行时断言（`len(_COMPRESS_THRESHOLD_TOKENS_ENV)==31` 且等于预期），不能凭输出截图定性。

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
- **卫生触发阈值（2026-08-02 P0 修复后）**：`agent_route_mixin.py` L322 `_compress_token_threshold = 200_000` **固定值**（替代旧的 `context_length × 0.85` = 850K）。
  **⚠️ 2026-09-16 更新（刘哥令「阈值 12万→30万」）**：该裸常量已改为 **tuned 键 `compressor.hygiene_token_threshold`**
  （helper `gateway/router/agent_route_mixin.py::_hygiene_token_threshold()`，**当前置位 `300000`**，缺键回退 `200_000`）。
  为什么改成键：本阈值**每会话每轮**读一次（非启动时读）⇒ 以后调它**不用改码 / 不用重启**。
  教训（本次实测）：卫生层比 agent 层**更早**拦会话 ⇒ 只把 agent 层阈值提到 30 万而卫生层仍 20 万时，
  30 万那条线**永远走不到**，观测会误读成「没变化」。改阈值必须**两层同改**（agent 层：`.env` 的
  `MIMIR_COMPRESS_THRESHOLD_TOKENS` + tuned `effective_window_tokens`；卫生层：本键）。
  取证全文：`~/.mimiraether/notes/2026-09-16-阈值12万到30万-变更记录.md`（含回滚三步 + 生效判据）。
  ⚠️ **2026-09-17 触发式验收新增（假绿族）**：**卫生层阈值 < agent 层阈值 ⇒ 卫生压缩结构性空转，却记 `outcome=applied`**。
  实证（`data/compression_quality.jsonl` 末行 · 11:38:55 · pid 112311）：`original_count 56 → compressed_count 56`（**一条没删**）、
  `summary_attempts 0`、`summary_mode "none"`、`entity_count 3`、`outcome "applied"`；日志侧只写
  `compressed 57 → 56 msgs, ~86,741 → ~14,555 tokens`（57→56 仅过滤 tool 消息；token 为粗估口径）。
  机理：卫生层按**自己的**阈值（本次 20,000）决定"要不要压"，但把活交给 agent 层 compressor，后者 `threshold_tokens`=**300,000**
  ⇒ `compress()` 首段"未达阈值即原样返回"⇒ 空转。⇒ **不是「调低卫生阈值就能压」，两层阈值必须满足卫生层 ≥ agent 层**。
  代价不只在假绿：本次空转仍在关键路径阻塞 **300.24s**（`[INDEX] hygiene-compress TIMEOUT ... worker abandoned`，全日志第 4 次）。
  取证：`~/.mimiraether/notes/2026-09-17-卫生压缩触发实验-结果与两个新发现.md`（含 A/B/C 三判据 + RS17 自证）。token 来源**仅用 actual**（`session_entry.last_prompt_tokens`），`estimated` 不再触发——旧估算偏差 3.05×（10:31 estimated 244,759 vs 10:34 actual 80,359）导致"该压不压"。消息数 ≥400 硬阀保留兜底。
- 优先使用 `session_entry.last_prompt_tokens`，否则用 `estimate_messages_tokens_rough(history)`。

### ⚠️ RS16 定位（2026-09-14 · `reason=no_api_key` = 凭据通路 provider 误绑定）

- **症状**：`[COMPRESS] abort layer=gateway reason=no_api_key msgs=323/327 tokens=201,213/209,356`（12:28:51 / 15:44:47）；且 **abort 后静默放行** —— `agent_route_mixin.py:430-464` 的 `result`/`reason=noop` 日志都在 `if api_key:` 块内 ⇒ 无 result 行，会话带 200K+ transcript 继续（F-A/D-2 只让失败变可见，能力缺口未变）。
- **根因**：`agent_route_mixin.py:371` → `_resolve_session_agent_runtime` → `gateway/_shared._resolve_runtime_agent_kwargs()` → `resolve_runtime_provider(requested=os.getenv("HERMES_INFERENCE_PROVIDER"))`。该 env **未设** ⇒ `"auto"` ⇒ `_resolve_openrouter_runtime()`（`mimir_cli/runtime_provider.py:420`）⇒ config.yaml `model` 无 `provider`/`base_url` ⇒ 落 OpenRouter 常量端点 ⇒ 候选 key 仅 `OPENROUTER_API_KEY`/`OPENAI_API_KEY`（均无）⇒ `api_key=""`。**该通路按构造看不到 `DEEPSEEK_API_KEY`**。
- **对照（为什么 agent 层能）**：agent/aux 走 Mimir 原生 `agent/provider_registry.resolve_api_key_provider_credentials("deepseek")`（`api_key_env_vars=('DEEPSEEK_API_KEY',)`）⇒ 有 key。**同一进程、两条互不相通的凭据通路**（§15「双血统路径」在凭据层的复现）。
- **受控差分判据**（决定性）：`~/.mimiraether/tmp/rs16_probe7.py` —— 注入 `.env` 的 DEEPSEEK key 前后，`_resolve_runtime_agent_kwargs()` **恒为 `provider=openrouter` / `api_key=EMPTY`**，而 registry 通路由 None → 非空。⇒ 「key 未传递」被否证，缺的是 provider 绑定。
- **修前必读**：`resolve_runtime_provider(requested="deepseek")` 直接 `AttributeError: 'NoneType' object has no attribute 'get'` @ `mimir_cli/runtime_provider.py:855`（`resolve_api_key_provider_credentials` 返回 None）⇒「把 `model.provider` 传给 hygiene」**修不通**，必须先修解析器。
- 完整报告：`~/.mimiraether/notes/2026-09-14-RS16-Q12-5branch-localization.md` · 卡 §22（`2026-09-14-四方审计-Mimir压缩永不应用根因与修复-RS14.md`）。

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

### ⚠️ T18 定案（2026-09-14 · 三处冷却全不可达 = 热重试环根因）

**结论先行**：`_SUMMARY_FAILURE_COOLDOWN` 这类冷却**在生产上从未生效过**。三处历史冷却全部不可达：

| # | 位置 | 机制 | 实测 |
|:-:|:--|:--|:--|
| 1 | `should_compress_info` L444 / L449 | `_last_compress_time` 冷却 + `_compress_failures>=2` | **全库零调用者**（只有 `__main__` demo 调 `should_compress`）⇒ 死代码 |
| 2 | `should_trigger_compression` L1582 | `time.time() < _summary_failure_cooldown_until` | **零调用者** + **时钟域错**（L707 写 `time.monotonic()`，L1582 读 `time.time()`；实测 1.79e9 < 5.5e4 ⇒ 恒 False） |
| 3 | `_generate_summary` L683 | `now < _summary_failure_cooldown_until` | **活**，但只在 LLM **抛异常**时武装（L707）；LLM 成功时 L698 **主动清零** ⇒ 闸门回滚（发生在 LLM 成功之后）**永不武装** |

**生产门只有一句**：`core_loop.py:907` / `agent_loop.py:647` → `needs_compression()` = `last_prompt_tokens >= threshold_tokens`，**无冷却、无回滚记忆**。回滚返回原 messages ⇒ token 不变 ⇒ **下一 turn 必然再次触发**（确定性环，非概率）。

**每 run 新建实例（H4b）**：`gateway/platforms/api_server.py:1538` 在 `_run_agent()`（L1508）体内调 `_create_agent()`，网关不按 session 缓存 agent ⇒ `core_loop.py:412` 每次新建 compressor ⇒ 实例内状态全归零。**纯实例内冷却跨 run 无效**，修法须跨 run 持久化（按 session 键）或做「上次因实体率回滚」的短路记忆。
**✅ 2026-09-22 更正（体检实测）**：该修法已落地为 **`agent/compress_cooldown.py`**——状态文件 `~/.mimiraether/data/ops/compress_cooldown.json`（+ `.json.lock` 锁 + tmp/replace 原子写）⇒ **跨 run 持久**。盘上实证（errors.log 2026-09-16）：`[COMPRESS] cooldown armed failures=1 delay=600s` / `failures=2 delay=1200s`，**同一 pid 跨两个不同 run 累加** ⇒ T18 的「实例内冷却跨 run 归零」已不成立。但注意：**近 5 天零压缩事件 ⇒ 该路径近 5 天未被行使**，"设计对"与"在生产被验证过"是两件事（撤回期 = 09-16）。

**规模**（`data/compression_quality.jsonl` 410 行 = 387 rollback + 23 applied）：19 个连续回滚串；rollback→rollback p50 **20.2s**、81.8% ≤35s；最大两串 ~84 次真 LLM 摘要、1,209s（20min）全部丢弃；rollback 中 mode=llm **155** / template 232 —— **sub-5s 串 = template 路径**（多数轮次没花钱），故表现为「稍快」而非「爆炸」。

**观测缺口**：`[COMPRESS]` 三态日志**不含 `pid=`**（agent.log 1,631 条 `[COMPRESS]` 行，`pid=` 命中 **0**）⇒ 压缩事件无法归因到 run；台账 18 字段**无 token 字段** ⇒ 摘要 token 成本**不可复算**（须先加埋点，勿凭「中段≈阈值」估算）。

⚠️ **行号顺序 ≠ 执行顺序**：`:1043` 的 `_last_compress_time` 赋值属**基类** `ContextCompressorV2.compress`（962–1069），由子类 `super().compress()`（:1331）**先跑完**；`:1378` 的闸门回滚在**子类** `MimirContextCompressor.compress`（1290–…）里更晚发生 ⇒ 该赋值**确实被执行**（只是没人查它 + 每 run 归零）。判「某行是否可达」必须先确认**类归属**与**覆写链执行序**。

完整取证：`~/.mimiraether/notes/2026-09-14-T18-压缩热环根因定案.md`（含 4 条探针自证）

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

> ⚠️ **2026-09-14 更正（RS14 · 盘上实测）**：下面这条「≥80% 实体可回溯」自检**在生产上恒不成立**，不要照它判「压缩质量 OK」——
> 实体按**整段 pre 的去重实体集**收集（实测 **32 条/会话**，见 `data/sessions/20260914_105712_994e2ffc.jsonl`：出现 50 / 去重 32），而中段必被摘要替换 ⇒ `data/compression_quality.jsonl` **275 条全 rollback（通过 0）**，**压缩自 08-24 起从未被应用过一次**。
> **两条独立真因**：① 摘要请求预算 `max_tokens*2` = 16000 ⇒ 必撞 30s 硬超时（盘上 `≥10` 例 `elapsed≈30.56/30.94/30.98/30.99s` **全是超时截断值，不是自然耗时** —— 拿它做延迟分布推断会循环论证）；② 闸门对「中段实体」结构性不可满足。
> **修复（commit `690d044`，未推送）**：C1 机器生成实体索引（llm/template 两条路都带）+ C2 输出预算夹到 4000（env `MIMIR_COMPRESS_SUMMARY_MAX_TOKENS`）。**生效须重启 gateway**（compressor 只在 `__init__` 读参 ⇒ 代码已提交 ≠ 已生效）。
> ✅ **2026-09-14 15:47:12 生产验证通过**（PID 402939 · 自然越线，非钉阈值）：`msgs 215->56 · tokens 120707->20445 · mode=llm · elapsed=20.42s` · `[P2-1] 实体保留率 89% OK` · 台账出现**首个 `outcome=applied`**（此前 300/300 rollback）⇒ **压缩自 08-24 起首次真正落地**。五项修复同帧实证：C2 `requested=13722 used=4000` / R5① `current_tokens=120707`（原恒 `None`）/ F-A `mode=llm`（原 95% template）/ RS12 `[TUNED-CLAMP]` / D-1 18 字段。
> **三条保留（勿下次又乐观）**：① **n=1**，非分布；`elapsed` 距 30s 墙仅 9.6s 余量。② **通关主因是 C1，不是摘要变好** —— rate 50~60%→88.57%，而 `index_items=24/index_chars=751`、上限 120/6000 **未绑定** ⇒ 闸门鉴别力被削弱（Loki Q1 同族风险）；**且仍真丢 4 个实体，全是 commit 哈希**（索引未收录 `commit <sha>`，待裁）。③ **代价真实**：压缩后 S2 前缀缓存短暂掉到 11.7%~17.5%，随即回升 98%+。
> **新发现（未擅动）**：gateway 层卫生压缩 `reason=no_api_key` 2 次（`gateway/router/agent_route_mixin.py:380`，与 agent 层两条独立路径）→ 建议立项 **RS16** 交四方裁。证据：卡 §16 · `~/.mimiraether/notes/2026-09-14-RS14-production-verified.md`
> **两个取证陷阱（本卡自曝）**：`missing` 落盘被截断为 `list(missing)[:5]`（`context_compressor.py:1345`）⇒ **历史 rate 不可复算**；索引上限 `_ENTITY_INDEX_MAX_ITEMS=120 / _ENTITY_INDEX_MAX_CHARS=6000` 在实测负载（仅需 **964 字符**）**永不绑定** ⇒ C1 后 rate ≡ 1.0，**闸门降级为「摘要消息+索引块是否存活」的结构检查**。另：阶段 1 掩码（修剪 tool 输出）对实体**零影响**（实测 97% 实体只在 assistant 段、tool 段 0 实体）——「掩码优先」不是实体保留方案。
> 完整四方审计：`~/wiki/discussions/2026-09-14-四方审计-Mimir压缩永不应用根因与修复-RS14.md`（Mimir 应答段 commit `04a0366`）· 决策记录：`~/.mimiraether/notes/2026-09-14-RS14-decisions.md`
> **D-1/D-2 执行（2026-09-14 · 四方终审 §13.2 P0）**：`compression_quality.jsonl` 现在
> **applied 与 rollback 两条路都落盘**，字段 18 个：`ts` / `gate_version` / `entity_retention_rate` /
> `entity_count` / `missing_count` / `missing`(全量, ≤`_QUALITY_MISSING_MAX_ITEMS`=200) / `missing_capped` /
> `index_items` / `index_chars` / `index_capped` / `summary_elapsed_s` / `requested_max_tokens` /
> `summary_budget_raw` / `summary_attempts` / `outcome` / `original_count` / `compressed_count` / `summary_mode`。
> **复算口径**：`rate = (entity_count - missing_count) / entity_count`（历史 `missing[:5]` 截断 ⇒ 不可复算）。
> **口径（D-2）**：闸门实体集 = **整段 pre 的去重集**（不是 HEAD 子集）；`gate_version = rs14.d1.v1.full-pre-set+r1>=0.80`，**跨版本率不可比**。
> **HEAD-only 恒真警告**：实测 HEAD 实体 = 0 ⇒ 只保留 HEAD 会让 `rate` 恒为 1.0（闸门失效）。
> 计数兜底：验证钩子被替换/抛异常时，`missing_count = max(统计值, len(missing))`、`entity_count = max(统计值, missing_count)` —— 绝不让 `entity_count=0` 与 `missing` 非空并存。
> 落点：`agent/context_compressor.py`（`ENTITY_GATE_VERSION` / `_QUALITY_MISSING_MAX_ITEMS` / `_entity_index_block` / `_generate_summary` / `_verify_entity_retention` / `_record_quality_alert`）· 测试 `tests/agent/test_rs14_d1_instrumentation.py`（10 条）。


**来源**: `docs/MEMORY_SELF_CHECK.md` — 压缩后实体保留率自检

每次 `compress()` 后检查:
```
1. 实体保留率（R1）: post 是否覆盖 **pre 全量去重实体集**
   （**不是** HEAD 子集 —— 实测 HEAD 实体 = 0，只留 HEAD = 闸门恒真）
   - 关键实体: 文件名 / 工具名 / 决策关键词 / 约束条件
   - 阈值: ≥80%（**RS14-D3 起降为结构检查 + 告警**；硬闸移到精确子集 100%）
   - <80% → 查 `missing` 明细 + 索引块是否存活（**勿**改 HEAD 保留、勿抬 tail 预算充数）

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

> **审计记录规则（2026-09-12 修：本规则旧版导致 41 行同质重复 · 42KB 技能里一半是噪声）**
> ① **只在「状态变化」时追加**：发现异常 / 修复 / 阈值或参数变动 / 根因定位 —— 一行，带盘上证据。
> ② **健康复核不再追加**：连通性复核（`auto-compress failed`=0 之类）结论恒定 → 不写（改了也是零增量）。
> ③ **同质行折叠**：本节历史同质健康行已折叠为下方单行汇总；此后若再现同质行，直接合并计数不新增行。
> ④ **攒批提交（2026-09-12 Hermes 实盘审计非阻塞建议 · 已采纳）**：单行审计轨迹**不逐行单推**——同类审计行（含两侧同步）**攒批合并为一个 commit 再推**，对齐「压 commit 不逐推」纪律（审计实测：当日 6 个单行审计 commit 使 GitHub 历史略碎）。例外：状态变化同时伴随代码/阈值改动时，仍按「代码+对应审计行」一并提交。


> ✅ 操作注记**更正**（2026-09-14 · B1 ACI 自查受控双探针）：2026-08-23 记的「skill_manage patch 报 Skill not found」**已不可复现**——负对照 `patch name=zzz-mimir-aci-negative-control-probe` → `Skill not found: <name>`；正样本 `patch name=mimiraether-context-compressor`（锚点=不可能存在的字符串）→ `old_string not found in skill`。两者**可区分** ⇒ `skill_manage` 对本人技能解析**正常**，且锚点缺失时**拒绝编辑**（无幻影改动）。
>
> 🔴 **写侧方向（2026-09-14 实测 · 我当场踩过）**：`skill_manage(action='patch')` 写入的是 **repo 侧**（`~/src/MimirAether/skills/...`），**不是** home 侧；而本注记下文（2026-08-23 版）称 home 侧"权威" ⇒ 若照旧文 `cp home→repo` 同步，会**把 skill_manage 的改动抹掉**（本轮已发生：patch 成功 → cp 后被清空 → 用 `patch` 工具对 home 侧重打同锚点恢复 → md5 双侧一致）。**正确同步方向 = 先改哪侧，就以哪侧为准 `cp` 到另一侧；改完必须 `grep` 关键串双侧各 1 次确认，不能只比 md5。**
> ⚠️ 操作注记（2026-08-23 · **保留供回溯，勿再据此绕过 skill_manage**）：需直接 patch 两侧文件：home 侧 `~/.mimiraether/skills/mimiraether/mimiraether-context-compressor/SKILL.md`（权威）与 repo 侧 `~/src/MimirAether/skills/mimiraether/mimiraether-context-compressor/SKILL.md`，改后 cp 同步 + diff 确认。嵌套目录 `mimiraether-context-compressor/mimiraether-context-compressor/` 为 187 行旧版，勿改勿覆盖。

| 日期 | 检查项 | 结果 |
|------|--------|------|
> **审计轨迹已迁出（2026-09-13 · B6 瘦身）**：本表原有 **34 行**（52122 B，占本文件 72%）
> 已整体迁至 **`~/.mimiraether/notes/2026-09-13-context-compressor-audit-trail.md`**，含全部历史审计行（2026-08-23 ~ 2026-09-13）。
>
> **为什么迁**：SKILL.md 的可达性 ≠ 体积；规则（①②③④）留在上面，逐行历史（大多数是已折叠的同质健康行 + 一次性取证长段）改由 notes 承载 ——
> 需要「当时怎么判的/证据是什么」时按实体名 grep 该 notes 文件即可（判据=关键事实可达性，已随迁验证）。
> **回滚**：`~/.mimiraether/backups/20260913-b6-skill-slim/home-SKILL.md.bak`（原 71876 B，sha256 见同目录 MANIFEST.json）。
>
> **迁移后新增审计行纪律（不变）**：仍按上方 ①②③④ —— 状态变化才写、健康复核不写、同质行折叠、攒批提交；新行追加到 notes 文件的**同构表格**里，SKILL.md 不再增长。
