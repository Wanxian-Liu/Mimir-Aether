# Compressor 重叠度审计

**日期**：2026-05-21  
**来源**：EV-P05（琬弦工程方案 §3.1）

## 两个 Compressor 对比

| 维度 | `agent/context_compressor.py` | `trajectory_compressor.py` |
|------|------|------|
| **行数** | 877 行 | 1507 行 |
| **运行时机** | 在线（每次对话） | 离线（批量处理存储轨迹） |
| **主类** | `ContextCompressorV2` | `TrajectoryCompressor` |
| **入口** | `compress()` — 压缩当前消息列表 | `compress_trajectory()` — 压缩离线轨迹 |
| **Token 估算** | `_estimate_tokens()` — 启发式 | `count_tokens()` — tokenizer |
| **摘要生成** | `_generate_summary()` — 在线 LLM | `_generate_summary()` — 批量 LLM |
| **保护逻辑** | `_sanitize_tool_pairs()` — 工具对完整性 | `_find_protected_indices()` — 受保护索引 |
| **摘要前缀** | `_with_prefix()` / `_with_summary_prefix()` | `_ensure_summary_prefix()` / `_coerce_summary_content()` |
| **配置** | 代码内常量 | `CompressionConfig` from YAML |

## 重叠点分析

| 重叠函数 | 重叠度 | 说明 |
|----------|:--:|------|
| Token 计数 | 🟡 30% | 同名不同法：context 用启发式、trajectory 用 tiktoken。无法直接共享 |
| 摘要生成 | 🟡 40% | 同名同类：都调 LLM 做摘要，但 context 在线（低延迟要求）、trajectory 离线（高精度优先） |
| 摘要前缀 | 🔴 70% | **可直接共享**：`_with_summary_prefix()` 和 `_ensure_summary_prefix()` 逻辑几乎一致 |
| 工具对保护 | 🟡 20% | 目标相似但实现不同：context 确保 tool_call+tool_result 成对，trajectory 保护 system/user 首尾 |
| 压缩配置 | 0% | 完全独立：context 内嵌常量，trajectory 读 YAML |

## 判定与建议

| 琬弦方案提议 | 实测 | 建议 |
|-------------|------|------|
| 合并两个 Compressor 的公共方法 | 实际重叠仅 **~30%**（摘要前缀共享），其余方法目标不同 | 🟡 只提取 `summary_prefix` 到共享模块；不合并整个类 |
| 提取 `compression_core.py` | 两个类的职责边界清晰（在线 vs 离线） | ⚠️ 不建议全量合并——拆分后两个场景的延迟/精度要求会互相妥协 |

## 结论

**重叠度约 30%**（方案假设可能高估了重叠）。核心原因：在线压缩（context）和离线压缩（trajectory）虽然都做"摘要"，但对延迟、精度、工具对完整性的约束完全不同。强行合并会引入不必要的耦合。
