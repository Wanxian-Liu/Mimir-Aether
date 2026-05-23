# EV-P05 — Compressor 重叠审计（2026-05-24）

> 只读 `rg`/`Read`；`agent/context_engine.py` **已移除**（EV-P03）。在线真源：`context_compressor` + 可选 CLI 插件槽。

## 摘要

- **两主实现**：在线 `MimirContextCompressor`（877 行）vs 离线 `TrajectoryCompressor`（1507 行）；生产 **0** import 轨迹压缩器。
- **重叠 ~30%**：摘要前缀**字符串已分叉**（`COMPACTION` vs `SUMMARY`），不宜整类合并；仍可抽共享 normalize 辅助函数。
- **插件 / mimicore**：仓库无 `plugins/context_engine/`；`get_plugin_context_engine` 仅 mimir_cli，**未接** `core_loop`。`mimicore` adaptive_compression **未**被 agent/gateway 生产 import。

**判定**：import>0 不可删；`context_engine` 文档漂移 → [dead-code-audit](./dead-code-audit.md)。

## A. 实现清单

| 实现 | 路径 | 在线/离线 | 调用方（代表） |
|------|------|-----------|----------------|
| 内置在线 | `agent/context_compressor.py` | 在线 | `core_loop` → `self.compressor.compress`；`gateway` `_compress_context`/`context_compressor`（router/command/agent_mixin）；`run_agent` 委托 |
| 离线轨迹 | `trajectory_compressor.py` | 离线 | **仅** `if __name__` + `fire.Fire(main)`；无 `import trajectory_compressor` |
| 插件引擎 | `plugins/context_engine/*`（运行时） | 在线（可选） | `mimir_cli/plugins_cmd._discover_context_engines`；**repo 内无包**；未替换 `MimirContextCompressor` |
| mimicore | `mimicore/{optimize,extractor}/adaptive_compression.py` | 记忆/索引子系统 | 仅 `mimicore/integrate/*`；**0** `agent|gateway|mimir_cli` import |

## B. 两主 Compressor 对比

| 维度 | `context_compressor.py` | `trajectory_compressor.py` |
|------|-------------------------|----------------------------|
| 行数 | 877 | 1507 |
| 主类 | `ContextCompressorV2` / **`MimirContextCompressor`** | `TrajectoryCompressor` |
| 入口 | `async compress()` | `compress_trajectory()` / `process_directory()` |
| Token | `_estimate_tokens`（chars/4 启发式） | `count_tokens`（HF tokenizer） |
| 摘要 LLM | `_generate_summary`（aiohttp/在线） | `_generate_summary`（OpenRouter 批量） |
| 保护 | `_sanitize_tool_pairs`（tool_call↔tool） | `_find_protected_indices`（头尾 turn） |
| 前缀 | `SUMMARY_PREFIX` + `_with_prefix` / `_with_summary_prefix` | `_ensure_summary_prefix` → **`[CONTEXT SUMMARY]:`** |
| 配置 | 模块常量 + `update_model()` 阈值 | `CompressionConfig` YAML |

## C. 重叠度（vs 2026-05-21）

| 项 | % | 说明 |
|----|---|------|
| Token 计数 | 30% | 同名异法；在线要快，离线要准 |
| 摘要 LLM | 40% | 都调 LLM；延迟/批量策略不同 |
| 摘要前缀 | **45%** | 逻辑类似但**前缀常量已不同**（2026-05-21 写 ~70% 可共享，今需先统一文案） |
| 工具对 vs 保护索引 | 20% | 目标不同，实现不可直接合并 |
| mimicore / 配置 | 0–5% | adaptive 仅 mimicore 内部；配置 YAML vs 常量，正交 |

**vs 2026-05-21**：行数不变；`context_engine.py` 已删（[dead-code-audit](./dead-code-audit.md)）；前缀分叉使共享难度↑。**Phase 1**：不合并整类；仅抽 prefix normalize（先统一文案）；插件须接 `core_loop` 才替换内置。
