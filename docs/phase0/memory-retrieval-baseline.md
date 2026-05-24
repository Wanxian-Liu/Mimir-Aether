# EV-A03 — Memory 检索基准（2026-05-24）

> **审计日** 2026-05-24 · 只读审计 + 本机 smoke。方法论旧稿：[`ARCHITECTURE_AUDIT_MEMORY_BENCHMARK.md`](../ARCHITECTURE_AUDIT_MEMORY_BENCHMARK.md)；可执行基准脚本 **Phase 1**（禁 `agent/memory_benchmark.py`）。

## 1. 检索路径（代码真源）

| 路径 | 模块/工具 | 机制 | 谁调用 | 数据位置 |
|------|-----------|------|--------|----------|
| **session_search** | `tools/session_search_tool.py` | **SQL `LIKE %query%`**（docstring 写 FTS5，实现无 FTS5 表） | Agent 工具 `toolsets`/`tools.registry`；`prompt_builder` 引导召回 | `$MIMIR_AETHER_HOME/data/sessions_search.db`（env `OPENCLAW_SESSION_DB` 可覆盖） |
| **fts5_search** | `tools/fts5_search/` | SQLite **FTS5** 虚拟表 + rank | **未接入生产**：`rg` 无 gateway/tier0/registry import；仅模块内 `test_engine.py` | 默认 `data/fts5_search.db`（引擎内 `get_mimir_data_dir()`） |
| **cross_session** | `agent/cross_session_memory.py` | JSON **全量 load/save**（identity/progress/decisions） | `core_loop` `_init_cross_session` / `_save_cross_session`；prompt 注入 | `$MIMIR_AETHER_HOME/data/persistent.json` |
| **memory 包** | `memory/memory_manager.py` + `providers/*` | 进程内 **list/dict**（Session/Working/Persistent/Skill）；**无全文检索** | `agent/__init__` 导出；`core_loop` 用 `memory.fencing`；与 `agent/memory_manager.py` **并存** | 运行时内存；Persistent provider 不落独立检索 DB |
| **prompt 直读** | `prompt_builder._build_cross_session_context` | JSON→XML | `build_system_prompt` | **`$MIMIR_AETHER_HOME/data/persistent.json`** + **`$MIMIR_AETHER_HOME/NEXT_SESSION.md`**（P1-M05，与 CrossSessionMemory 对齐） |
| **tool_quality** | `tool_quality.db` | SQL 聚合（非 transcript） | IQ 审计 | `$MIMIR_AETHER_HOME/data/tool_quality.db` |

孤儿：`agent/memory_system.py`（0 import，见 [`dead-code-audit.md`](./dead-code-audit.md)）。

## 2. 本机 smoke（2026-05-24）

| 检查 | 结果 |
|------|------|
| `ls …/data/*.db` | `sessions_search.db` (24KB)、`tool_quality.db` (45KB) |
| `persistent.json` | 存在 (~18KB) |
| `sessions_search` 行数 | **messages=0, sessions=0**（库空 → 基准 hit 不可信） |
| `session_search("persistent"\|"Gateway"\|"tool call")` | **0 hit**，P50 **&lt;1ms** |

## 3. 20 条 Query（Gold = 期望命中片段，一句话）

| # | Query | 类型 | Gold label |
|---|-------|------|------------|
| 1 | `persistent.json 截断` | 精确关键字 | 提及 persistent 写入/截断或 merge 冲突的会话或 ADR 片段 |
| 2 | `tool call 格式 DeepSeek` | 精确关键字 | DeepSeek/OpenAI tool_calls 兼容或修复记录 |
| 3 | `run_ralph_tier0` | 精确关键字 | tier0 门禁或 Gate2/3 计数说明 |
| 4 | `MIMIR_AETHER_HOME` | 精确关键字 | path-contract 或 runtime home 与 clone 分离说明 |
| 5 | `237+2` | 精确关键字 | tier0 用例规模或 E-010/E-011 回归提及 |
| 6 | `架构方案 琬弦` | 语义模糊中文 | 统一计划/Phase 方向或 Memory 升级讨论 |
| 7 | `Gateway 崩溃怎么恢复` | 语义模糊中文 | gateway 重启、IR 恢复或 OPERATIONS 步骤 |
| 8 | `跨会话记忆 上次在做什么` | 语义模糊中文 | `persistent.json` progress / current_objective |
| 9 | `压缩 上下文 重叠` | 语义模糊中文 | compressor vs summary 分叉或 EV-P05 结论 |
| 10 | `智商评分 rubric` | 语义模糊中文 | IQ ~3.8/10 或四维度评分表 |
| 11 | `memory leak session` | 中英混合 | 内存/会话泄漏或 fencing 相关讨论 |
| 12 | `FTS5 semantic search` | 中英混合 | fts5_search 模块或 LIKE→语义升级计划 |
| 13 | `CrossSessionMemory save` | 中英混合 | `cross_session_memory.py` save/merge 行为 |
| 14 | `2026-05-20 IR` | 时间/会话限定 | IR-20260520 工程结案或 handoff 条目 |
| 15 | `last_session_end` | 时间/会话限定 | persistent 中上次结束时间字段 |
| 16 | `session_id feishu` | 时间/会话限定 | 飞书 channel 会话或 gateway session 元数据 |
| 17 | `IR-20260520` | 工具/事件专有 | IR 事故根因/恢复条目 |
| 18 | `E-008 cli shim` | 工具/事件专有 | cli.py 薄 shim / mimir_cli 迁移 |
| 19 | `JEPA` | 工具/事件专有 | JEPA/预测相关计划或 mimicore 文档（若曾写入 transcript） |
| 20 | `EV-A03 memory benchmark` | 工具/事件专有 | 本基准或 ARCHITECTURE_AUDIT_MEMORY_BENCHMARK 方法论 |

## 4. 结论（P1-LONG-MEM 结案 · 2026-05-24）

**Phase 1 交付（M01～M05，main `7f4b53d`+）**

| 子项 | 交付物 |
|------|--------|
| **M01** | `session_search_indexer`、backfill、20-query 基准脚本 + JSON |
| **M02** | 合入 + M6 + tier0 绿 |
| **M03** | Gateway `append_to_transcript` / rewrite → `sessions_search.db`（`MIMIR_SESSION_SEARCH_INDEX=0` 可关） |
| **M04** | `SESSION_SEARCH_BACKEND=fts5\|hybrid`；`prepare_fts5_match_query`（hyphen/dot 无 SQL 错） |
| **M05** | `prompt_builder._build_cross_session_context` → `get_mimir_data_dir()` / `get_mimir_home()`（与 CrossSessionMemory 同路径） |

**生产检索**：默认 **LIKE**；推荐 **`SESSION_SEARCH_BACKEND=hybrid`**（FTS5 优先，零命中回退 LIKE）。`fts5` 仅用 `fts5_search.db`。

**2026-05-24 基准**（`memory-retrieval-benchmark-20260524.json`，回填后）：LIKE **60%** / FTS **50%** 会话命中率（20 query）；FTS 未达 ≥LIKE（CJK 多词与部分英文短语在 FTS5 tokenizer 上弱于 LIKE 子串）。

**明确不做（Phase 2）**：**semantic / chromadb 检索** → **`P2-LONG-SEM`**；统一 `memory_benchmark` 工具仍为后续项。
