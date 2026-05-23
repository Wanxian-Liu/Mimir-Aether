# EV-Q02 — ToolQuality 基线（2026-05-24）

> 模块 `agent/tool_quality.py` **314** 行；DB `$MIMIR_AETHER_HOME/data/tool_quality.db`（表 `tool_quality`，无独立 `executions` 表）。

## 摘要

- **非空壳**：SQLite WAL + 滚动 **20** 条/工具 + `evolve_interval=10` + `get_degraded_tools(0.5)`。
- **生产 import**：`execution_pipeline` / `execution_pipeline_sessions`、`skill_evolution`、`jepa_session_hook`（候选文件）。
- **快照**（2026-05-24，`~/.mimiraether`）：17 工具行；多为 tier0/测试 echo。

## 架构

| 项 | 值 |
|----|-----|
| 存储 | `tool_quality` 表（JSON `recent_executions`） |
| 窗口 | `ToolQualityRecord.MAX_RECENT = 20` |
| 演进 | 每 **10** 次全局 `record` → `should_evolve()` |
| 降级 | `total_calls≥3` 且 `quality_score<0.5` |

## TOP10 快照（total_calls 降序）

| tool | n | ok% | avg_ms† |
|------|--:|----:|--------:|
| echo | 259 | 100 | ~0.5 |
| read_file | 38 | 100 | ~930 |
| crash_tool | 21 | 0 | ~0.5 |
| calc | 21 | 100 | ~0.3 |
| orphan_tool | 21 | 0 | ~0.2 |
| tool_b | 21 | 100 | ~0.4 |
| search_files | 11 | 100 | ~720 |
| terminal | 9 | 100 | ~6000‡ |
| web_extract | 5 | 100 | ~35000‡ |
| web_search | 4 | 100 | ~2100 |

† `total_duration_ms/total_calls`；‡ 含长尾单次。

## vs 2026-05-21 / Phase 1

旧稿「待查 DB」→ 已有数据（偏测试）。**ToolPromptOptimizer** 可直接读 `rank_tools()` / `get_degraded_tools()`；生产工具需更多真实 gateway 流量稀释 echo 噪声。
