# ENG-WF-20: 上下文三套 Inventory

> **真源**：北星 §3 阶段 1b · 只读调查，**不实施**
> **日期**：2026-06-01 · **Commit**：`eb68004`

---

## 1. conversation_history（≈ `conversation_formatter.py` + `conversation_nudges.py`）

| 条目 | 内容 |
|------|------|
| **真源文件** | `agent/conversation_formatter.py`（218 行）+ `agent/conversation_nudges.py` |
| **职责** | 执行后分析：JSONL 轨迹 → 结构化文本（优先级截断、错误检测、摘要提取） |
| **重叠** | `context_compressor` 也做截断 → 两者截断策略可能冲突 |
| **建议** | `conversation_formatter` 专注**存档/导出**，`context_compressor` 专注**运行时** |

## 2. context_compressor（`context_compressor.py`）

| 条目 | 内容 |
|------|------|
| **真源文件** | `agent/context_compressor.py`（884 行）V2.3 |
| **职责** | 运行时上下文压缩（退化检测、决策降权、summary 注入、multi-turn 裁剪） |
| **重叠** | 与 `conversation_formatter` 的优先级截断策略重叠；与 `degeneration_guard` 的退化检测重叠 |
| **建议** | 收敛到固定入口：`compress_for_model_call()` + 禁用退化的旁路 |

## 3. recovery（`recovery.py` + `recovery_mixin.py`）

| 条目 | 内容 |
|------|------|
| **真源文件** | `agent/recovery.py`（251 行）+ `agent/recovery_mixin.py`（265 行） |
| **职责** | `recovery.py`：工具/API 错误的标准恢复策略；`recovery_mixin.py`：Mixin 注入 MimirAetherAgent |
| **重叠** | `error_classifier.py`（957 行）也做错误分类和恢复；`config_mixin.py` 也有恢复逻辑 |
| **建议** | 统一到 `recovery.py`，去掉 `recovery_mixin.py` 和 `error_classifier.py` 中的重复恢复分支 |

---

## 综合

| 模块 | LOC | 独立 | 重叠模块 | 收敛建议 |
|:----:|:---:|:----:|:--------:|:--------:|
| conversation_formatter | 218 | ✅ | context_compressor | 存档导出 vs 运行时 |
| context_compressor | 884 | ✅ | conversation_formatter, degeneration_guard | 统一入口 + 旁路 |
| recovery + mixin | 516 | ❌ 重叠大 | error_classifier(957行), config_mixin | 三合一到 recovery.py |
