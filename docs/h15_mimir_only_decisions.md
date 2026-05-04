# H15：`mimir_only` 工具名 — 对齐 Hermes 决策表（文档）

**用途**：为 [`scripts/diff_tool_names_hermes_mimir.py`](../scripts/diff_tool_names_hermes_mimir.py) 输出的 **`mimir_only`** 名称逐条登记 **对齐策略**，供产品 / 维护者裁决与后续实现（改名、别名、toolset 分层、永久 DIFF）引用。

**基线快照**（名级 diff 来源）：[`docs/parity_snapshots/h15_tool_names_diff_20260501.json`](parity_snapshots/h15_tool_names_diff_20260501.json)（**25** 条 `mimir_only`；`hermes_only` 仅为 **`feishu_*`×5**）。历史：`h15_tool_names_diff_20260506.json`（26 条，含已对齐的 `search_web`）。

## 已落实（名级）

| 原 / 议题 | 实现 |
|-----------|------|
| `search_web` vs `web_search` | **`search_web` 不再注册**；对外名与 Hermes 一致为 **`web_search`**。`mimir_web` toolset 已改为 `web_search`。旧模型若仍调用 `search_web`：`model_tools` 在 discovery 后 **`register_tool_remap("search_web", "web_search")`**；主循环在 `registry.dispatch` 前执行 **`route_tool_call`**（与 `handle_function_call` 一致）。 |
| `set_strategy` | **文档化 DIFF（永久）**：Mimir 行为策略切换；不要求 Hermes 同名工具。 |

**行为矩阵锚点**：[`hermes_mimir_behavior_matrix.md`](hermes_mimir_behavior_matrix.md) **H15**。

**默认核心工具列表**（Mimir 侧跨平台常用集合，**不等于** Hermes `get_tool_definitions`）：[`toolsets.py`](../toolsets.py) 中 **`_HERMES_CORE_TOOLS`** — 下表 **「在默认 core」** 指名称是否出现在该列表。

---

## 决策取值（四选一 + 待裁决）

| 取值 | 含义 |
|------|------|
| **文档化 DIFF** | 接受「仅 Mimir / OpenClaw 暴露」；不追求与 Hermes **工具名集合**一致；矩阵与快照持续标注。 |
| **改名 / 别名对齐** | 目标：与 Hermes **同名**或 **稳定别名**（实现可后移；本表只记意图）。 |
| **移出默认暴露** | 目标：在「Hermes 对齐模式」或等价 **窄 toolset** 中 **默认不下发**（仍可实现侧保留注册）。 |
| **待裁决** | 需负责人选 **文档化 DIFF / 改名 / 移出默认** 之一；未定前不宣称名级对齐。 |

---

## 决策表（按工具名）

> **说明**：「建议」列为协作者根据当前架构写的 **默认推荐**，可整表覆写为团队决议。

| 工具名 | 域 / 粗分类 | 在默认 core（`_HERMES_CORE_TOOLS`） | 决策（建议） | 备注 |
|--------|-------------|--------------------------------------|--------------|------|
| `get_env` | 运行环境只读查询 | 否 | **文档化 DIFF** | 典型 OpenClaw / 宿主集成能力；Hermes 未必暴露等价工具名。 |
| `set_strategy` | 策略 / 模式切换 | 否 | **文档化 DIFF** | Mimir 编排语义；不追求 Hermes 名级对齐（见 §已落实）。 |
| `cronjob` | 定时任务 | 是 | **文档化 DIFF** | 已在 Mimir 默认 core；Hermes 工具管道未包含时视为 **扩展面**。 |
| `send_message` | 跨平台发消息（网关 gating） | 是 | **文档化 DIFF** | 强依赖 Mimir gateway / 适配器；与 Hermes **名级**一致非必须，除非产品要求「同提示词跨仓」。 |
| `text_to_speech` | TTS | 是 | **文档化 DIFF** | 能力可保留；名级对齐低优先级，除非 Hermes 增加同名定义。 |
| `vision_analyze` | 视觉分析 | 是 | **文档化 DIFF** | 同上。 |
| `ha_list_entities` | Home Assistant | 是 | **文档化 DIFF** | 可选集成；**移出默认暴露** 可作为「Hermes 窄模式」备选项（当前仅记建议）。 |
| `ha_get_state` | Home Assistant | 是 | **文档化 DIFF** | 同上。 |
| `ha_list_services` | Home Assistant | 是 | **文档化 DIFF** | 同上。 |
| `ha_call_service` | Home Assistant | 是 | **文档化 DIFF** | 同上。 |
| `mixture_of_agents` | MoA 推理 | 否（在 `moa` toolset） | **文档化 DIFF** | 高级编排；默认不进入 Hermes 名级对齐范围，除非产品明确要 **移出默认暴露** 或 **对齐**。 |
| `produce_capsule` | MimiCore 胶囊 | 否 | **文档化 DIFF** | Mimir 域知识沉淀；**移出默认暴露** 可作为 Hermes 对齐模式选项。 |
| `get_capsule_by_id` | MimiCore 胶囊 | 否 | **文档化 DIFF** | 同上。 |
| `list_capsules` | MimiCore 胶囊 | 否 | **文档化 DIFF** | 同上。 |
| `improve_capsule` | MimiCore 胶囊 | 否 | **文档化 DIFF** | 同上。 |
| `rl_list_environments` | RL / OpenClaw 训练 | 否 | **文档化 DIFF** | 典型扩展工具面；Hermes 对齐模式下建议 **移出默认暴露**（可选）。 |
| `rl_select_environment` | RL | 否 | **文档化 DIFF** | 同上。 |
| `rl_get_current_config` | RL | 否 | **文档化 DIFF** | 同上。 |
| `rl_edit_config` | RL | 否 | **文档化 DIFF** | 同上。 |
| `rl_start_training` | RL | 否 | **文档化 DIFF** | 同上。 |
| `rl_stop_training` | RL | 否 | **文档化 DIFF** | 同上。 |
| `rl_check_status` | RL | 否 | **文档化 DIFF** | 同上。 |
| `rl_list_runs` | RL | 否 | **文档化 DIFF** | 同上。 |
| `rl_get_results` | RL | 否 | **文档化 DIFF** | 同上。 |
| `rl_test_inference` | RL | 否 | **文档化 DIFF** | 同上。 |

---

## 与 `hermes_only`（Feishu）的关系（不在本表逐条展开）

当前 **`feishu_*`（5）** 仅在 Hermes 侧出现：若产品目标是 **面级 Hermes 对齐**，需 **另表** 决策「是否在 Mimir 实现 / 镜像工具名」；本文件仅覆盖 **`mimir_only`**。

---

## 维护规则

1. **更新名级 diff 快照**后：核对本表行数与 `mimir_only` 列表一致；新增工具 **默认「待裁决」** 直至补全决策列。  
2. **实现改名 / toolset 变更**后：更新本表 **决策** 与 **备注**，并同步 **H15** 脚注或 [`parity_snapshots/`](parity_snapshots/) 元数据。  
3. **代码变更**：独立 PR + **`./run_ralph_tier0.sh`** +（若触及受保护路径）**`record_m6_evolution.sh`**；同步更新本表与快照。

---

## 修订记录

| 日期 | 变更 |
|------|------|
| 2026-05-05 | 初版：26 条 `mimir_only` 决策建议表；链接 H15 快照与 `toolsets._HERMES_CORE_TOOLS`。 |
| 2026-05-01 | `search_web` 对齐 `web_search`（代码 + remap）；`set_strategy` 定为文档化 DIFF；快照 **25** 条 `mimir_only`。 |
