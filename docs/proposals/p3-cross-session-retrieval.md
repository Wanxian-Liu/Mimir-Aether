# P3 — 跨会话检索与分层注入（调研提案）

> **Grain:** `P3-XSR-01` · Wave 14 Task 11  
> **状态:** 提案轨（**无生产代码切换**）  
> **日期:** 2026-05-27  
> **父项:** `docs/MIMIR_EXEC_BACKLOG.md` §8 `P3-CROSS-SESSION-RETRIEVAL` · §18.2 / §19.1  
> **Gate:** 需刘哥拍板 **G-ADR-002** 后再开写入/注入扩展实现（见 §6）

---

## 1. 问题陈述

Mimir 当前跨会话上下文有两条轨，但**缺少「按问题自动捞历史」的统一策略**：

| 轨 | 机制 | 典型体积 | 何时进入 prompt |
|----|------|----------|-----------------|
| **A. 热注入** | `_build_cross_session_context()` 读 runtime `persistent.json` + `NEXT_SESSION.md` | ~0.5–2K 字符（`MIMIR_CROSS_SESSION_MAX_CHARS` 默认 2000） | 每轮 system prompt **自动** |
| **B. 冷检索** | `session_search`（LIKE / FTS5 / semantic / semantic_hybrid + OS-SCH-02 RRF） | 按需，工具结果 | Agent **主动**调工具；prompt 有 search-first 引导 |

**缺口：** 用户问「上次世界模型论文聊了什么」时，A 轨只有 `key_decisions` 等摘要（IQ-EVO-49 粒 B），若没有事先写入摘要，B 轨依赖模型记得调 `session_search`。没有「新会话启动时按 objective 预取 Top-N  transcript 片段」或「与 capsules 统一的 RAG 层」。

本提案定义 **三层注入模型**，对照 Hermes，并说明与 **ADR-002** 的边界，供 Gate 拍板后由 `ENGINE-P3W-01` / 后续 Wave 实现。

---

## 2. 三层注入模型（建议真源）

```text
┌─────────────────────────────────────────────────────────────┐
│  L1 核心全量（Core slice）— 已有，继续 cap                     │
│  persistent progress + key_decisions + learned_patterns      │
│  + NEXT_SESSION + context_usage hint                         │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  L2 相关 Top-N（Retrieval slice）— 半自动                    │
│  用「当前 objective / 用户首条 / 上轮摘要」构造 query         │
│  → session_search(limit=N) 或内部等价 API（不经 LLM 工具）    │
│  → 注入 <retrieved-sessions> 块（有界字符）                   │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  L3 语义 RAG（Semantic slice）— 可选、重                      │
│  Chroma / semantic_hybrid 对 transcripts + 可选 capsules     │
│  与 L2 复用 OS-SCH-02 RRF；**不**替代 L1                     │
└─────────────────────────────────────────────────────────────┘
```

### 2.1 L1 — 核心全量（Core）

**现状（已实现）：**

- `agent/prompt_builder._build_cross_session_context`（ADR-002 注入切片）
- 字段：`progress`、`memory.key_decisions`（默认 5）、`learned_patterns`（默认 3）、`curator_nudge`、`session_count`、`NEXT_SESSION.md`
- 总 cap：`MIMIR_CROSS_SESSION_MAX_CHARS`（默认 2000）

**建议（实现阶段，非本粒）：**

- 保持 L1 **小而稳**；不把 `persistent.json` 全文塞进 prompt（~12KB+ 会挤占工具上下文）。
- 新事实仍走 **capsules**（HTML）或 **curator 写入** persistent 子段（ADR-002 写路径）。

### 2.2 L2 — 相关 Top-N（Retrieval）

**目标：** 在新会话或 `/new` 后首轮，用**确定性检索**补 L1 摘要不覆盖的 transcript 细节。

| 项 | 建议 |
|----|------|
| **Query 来源** | `progress.current_objective`；若无则 `NEXT_SESSION` 首段；再无则跳过 L2 |
| **后端** | 复用 `session_search()`，默认 **`SESSION_SEARCH_BACKEND=hybrid`**（与 P2-LONG-SEM 一致）；**本提案不修改生产 env 默认** |
| **融合** | 已有 `MIMIR_SESSION_SEARCH_FUSION=1` + `rank_fusion_rrf`（OS-SCH-02） |
| **预算** | 新 env `MIMIR_CROSS_SESSION_RETRIEVAL_MAX_CHARS`（建议 1500–3000）；Top **2–3** sessions，每 session **1** 摘要块 |
| **触发** | 仅 gateway 新 session / `session_reset` 后第一次 `build_system_prompt`；避免每轮重复检索 |
| **与工具关系** | L2 为 **系统预取**；`session_search` 工具仍保留给 search-first 深搜 |

### 2.3 L3 — 语义 RAG（Semantic）

**目标：** 模糊问法（「之前架构讨论」「上次和刘哥定的方向」）在 L2 词法弱时补语义命中。

| 项 | 建议 |
|----|------|
| **索引** | 已有 `tools/chroma_session_indexer` + `semantic_hybrid` 路径 |
| **范围** | Phase 2a：仅 **transcript**；Phase 2b：可选 **capsule 文本** 入同一 collection（需 ADR-002 写路径稳定） |
| **注入** | 与 L2 合并为同一 `<retrieved-sessions>` 或分 `<semantic-recall>`；RRF 合并 lexical+semantic 排名 |
| **成本** | Embedding 延迟 + Chroma 磁盘；需 feature flag `MIMIR_CROSS_SESSION_RAG=0` 默认 **关** |

---

## 3. Mimir 现状快照（2026-05-27）

| 能力 | 状态 | 引用 |
|------|------|------|
| L1 cross-session 块 | ✅ | `prompt_builder._build_cross_session_context` |
| search-first 引导 | ✅ | `SESSION_SEARCH_GUIDANCE` |
| session_search 多后端 | ✅ | `tools/session_search_tool.py` · ADR-006 |
| Gateway 增量索引 | ✅ | `gateway/session.py` · P1-M03 |
| semantic + RRF | ✅ | OS-SCH-02 · `semantic_hybrid` |
| tool_search 发现工具 | ✅ | OS-TOOL-SRCH-01 |
| L2 自动预取注入 | ❌ | 本提案 |
| L3 自动语义预取 | ❌ | 本提案 |
| 统一 MemoryFacade 读写 | ❌ deferred | ADR-002 stub · spike |

检索基准与 20-query gold：`docs/phase0/memory-retrieval-baseline.md` · `run_memory_retrieval_benchmark.py`。

---

## 4. Hermes 注入策略对照

来源：`docs/hermes-comparison-detailed.md` §6.18 · §6.22 · §6 记忆相关行。

| 维度 | Hermes（上游） | Mimir（本仓） | 对本提案的启示 |
|------|----------------|---------------|----------------|
| **Prompt 分层** | stable / context / volatile 显式三层 | 单文件 `prompt_builder`，volatile 含 cross-session | 可把 L1/L2/L3 放进 **volatile 子块**，不必先拆文件 |
| **跨会话注入** | memory snapshot 注入 | `<cross-session-context>` JSON 摘要 | 持平；Mimir L1 更结构化（decisions/patterns） |
| **历史 transcript** | 依赖 provider / 工具链 | **search-first** + `session_search` 工具 | Hermes 无等价「强制先搜」句；Mimir 行为引导更强 |
| **语义检索** | 因部署而异 | Chroma + hybrid/semantic_hybrid（P2-LONG-SEM） | Mimir L3 有实现基础 |
| **记忆写入** | provider 分散 | capsules + persistent + wiki（ADR-002） | 先 Gate 写路径，再扩 RAG 索引源 |

**结论：** Hermes 强在 **prompt 分层清晰度**；Mimir 强在 **检索链路与 search-first**。三层模型是 Mimir 侧对「snapshot + 按需搜」的显式化，不是照搬 Hermes 目录结构。

---

## 5. 与 ADR-002 的关系（Gate G-ADR-002）

| 主题 | ADR-002 已决（spike/stub） | 本提案（P3-XSR） |
|------|---------------------------|------------------|
| **写路径** | A 胶囊 / B persistent / C wiki；统一 Facade **deferred** | **不新增写路径** |
| **读/注入路径** | L1 已用 persistent 子集注入 | 提议增加 L2/L3 **读** transcript / Chroma |
| **单写者** | ADR-001 / IND-05 persistent 单写者 | 只读检索不写 persistent |
| **ISSUES #3** | deferred 实现 | 本提案不关闭 #3 |

**提交刘哥 Gate G-ADR-002 的决策点：**

1. **是否批准 L2**（新会话自动 `session_search` 预取注入）在 cap 内进入 prompt？  
2. **是否批准 L3**（语义预取）作为独立 flag，默认 off？  
3. **L2/L3 与 ADR-002 统一 Facade 的先后顺序**：建议 **先 L2（仅读 session_search）→ Gate 通过后 L3 → 最后 MemoryFacade 写路径统一**（`ENGINE-P3W-01`）。

未批准前：**禁止**改 `SESSION_SEARCH_BACKEND` 生产默认、禁止默认开启 `MIMIR_CROSS_SESSION_RAG`。

---

## 6. 建议实施顺序（工程轨，非本粒）

| 阶段 | 交付 | 依赖 | 验证 |
|------|------|------|------|
| **P3-XSR-01** | 本文档 + closeout | — | tier0 契约 |
| **P3-XSR-02**（候选） | L2：`prompt_builder` 预取 + env + 单测 | G-ADR-002 ✅ | tier0 · `/new` 冒烟 |
| **P3-XSR-03**（候选） | L3：RAG flag + 与 L2 合并注入 | Chroma 索引健康 | `run_memory_retrieval_benchmark` 不退化 |
| **ENGINE-P3W-01** | ADR-002 写路径 Facade | ADR-001 | 与 L3 capsule 索引对齐 |

---

## 7. 非目标（本提案明确不做）

- 不改 **`SESSION_SEARCH_BACKEND`** 生产默认值（保持现网/文档约定：`hybrid` 为推荐，非强制改 env）。
- 不实现 **WM Phase 0** 世界模型预测注入。
- 不提交 **`data/persistent.json`** 或扩大 L1 为全文注入。
- 不替代 **`session_search` 工具**；search-first 行为保持。
- 不在本粒做 **ADR-002 写入统一**（仅引用 Gate）。

---

## 8. 验收标准（实现阶段用）

| 检查 | 标准 |
|------|------|
| L1 回归 | `/new` 后仍见 `key_decisions`（IQ-EVO-49） |
| L2 | 有 objective 时 prompt 含 `<retrieved-sessions>` 且字符 ≤ cap |
| L2 否 | 无 query 源时不调 session_search（无空转） |
| L3 | `MIMIR_CROSS_SESSION_RAG=0` 时行为与仅 L2 一致 |
| 检索质量 | `run_evolution_eval` / 20-query 不低于基线 −5pp |
| Parity | `./run_ralph_tier0.sh` 绿 |

---

## 9. 参考

- [`docs/hermes-comparison-detailed.md`](../hermes-comparison-detailed.md) — §6.18 prompt · §6.22 memory  
- [`docs/phase0/memory-retrieval-baseline.md`](../phase0/memory-retrieval-baseline.md)  
- [`docs/phase0/adr-002-write-spike.md`](../phase0/adr-002-write-spike.md) · [`docs/adr/002-memory-write-paths.md`](../adr/002-memory-write-paths.md)  
- [`docs/phase0/iqevo-49-grain-b-cross-session-closeout.md`](../phase0/iqevo-49-grain-b-cross-session-closeout.md)  
- [`docs/adr/006-semantic-memory-chromadb.md`](../adr/006-semantic-memory-chromadb.md)  
- [`docs/phase0/os-sch-02-closeout.md`](../phase0/os-sch-02-closeout.md)  
- [`docs/MIMIR_IQ_EVOLUTION_DIRECTION.md`](../MIMIR_IQ_EVOLUTION_DIRECTION.md) — IQ rubric 回忆维度
