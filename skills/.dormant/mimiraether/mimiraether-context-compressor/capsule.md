# [DORMANT] mimiraether-context-compressor

**沉寂时间**: 2026-11-21T06:40:45.557700+00:00
**原始分类**: mimiraether
**描述**: MimirAether 上下文压缩：本仓库 agent/context_compressor 行为、MimirAetherAgent 参数、Gateway 卫生压缩与配置键（与运行时对齐）。
**触发阈值**: 60天未触碰

---

## 技能要点

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

**B9 一等公民上限（2026-09-13 · commit `41fd67c`）**：`resolve_threshold_tokens()` 在 percent/env 解析之后追加一层夹紧 —— `threshold = min(configured, tuned "compressor.effective_window_tokens", floor(0.75 × context_length))`。**tuned 键缺失 ⇒ 该层完全不生效**（严格向后兼容）。当前（**2026-09-22 全身体检实测更新 · 原文已过期**）真源 = **`~/.mimiraether/d

... (truncated)

---

> 此胶囊由 Skill Curator 自动生成。原始技能已移入 .dormant/。
> 调用 `skill_view("mimiraether-context-compressor")` 即可自动唤醒。
