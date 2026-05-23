# Phase 0 执行队列 — Mimir 真相图谱

> **系列名**：Phase 0 — Mimir 真相图谱（只读审计，**禁止**改 `agent/` / `gateway/` / `mimir_cli/`）  
> **来源**：[`docs/MIMIR_UNIFIED_PLAN.md`](./MIMIR_UNIFIED_PLAN.md) §2（14 粒）  
> **规则**：一次一粒；完成后标 `[x] YYYY-MM-DD`；产出写入 `docs/phase0/<slug>.md`  
> **整系列完成后**：再排 Phase 1 工程（测试/GOD 拆分等）与 Phase 2 架构（persistent 单写者、Core 重划等）  
> **唯一 Active 执行源**：本表第一条 `[ ]` 行（勿再读 `MIMIR_EXEC_BACKLOG.md` §2）

| ID | 名称 | 产出路径 | 估时 | 状态 |
|----|------|----------|------|------|
| EV-P01 | fixtures 目录+README+示例 | [docs/phase0/fixtures-readme.md](./phase0/fixtures-readme.md) | 15min | [x] 2026-05-24 |
| EV-P02 | 测试命名规范 | [docs/phase0/test-naming-convention.md](./phase0/test-naming-convention.md) | 10min | [x] 2026-05-24 |
| EV-P03 | 废弃代码审计 | [docs/phase0/dead-code-audit.md](./phase0/dead-code-audit.md) | 20min | [x] 2026-05-24 |
| EV-P04 | GOD 文件清单 | [docs/phase0/god-file-inventory.md](./phase0/god-file-inventory.md) | 15min | [x] 2026-05-24 |
| EV-P05 | Compressor 重叠审计 | [docs/phase0/compressor-overlap-audit.md](./phase0/compressor-overlap-audit.md) | 20min | [x] 2026-05-24 |
| EV-A01 | Agent Core 职责映射 | [docs/phase0/agent-core-responsibility-map.md](./phase0/agent-core-responsibility-map.md) | 40min | [x] 2026-05-24 |
| EV-A02 | Mimicore 依赖摸底 | [docs/phase0/mimicore-import-audit.md](./phase0/mimicore-import-audit.md) | 15min | [x] 2026-05-24 |
| EV-A03 | Memory 检索基准 | [docs/phase0/memory-retrieval-baseline.md](./phase0/memory-retrieval-baseline.md) | 30min | [x] 2026-05-24 |
| EV-A04 | 架构评分方法论 | [docs/phase0/architecture-scoring-rubric.md](./phase0/architecture-scoring-rubric.md) | 15min | [x] 2026-05-24 |
| EV-A05 | prompt_builder 安全审计 | [docs/phase0/prompt-builder-security-audit.md](./phase0/prompt-builder-security-audit.md) | 15min | [x] 2026-05-24 |
| EV-Q01 | 硬编码阈值清单 | [docs/phase0/hardcoded-thresholds.md](./phase0/hardcoded-thresholds.md) | 15min | [x] 2026-05-24 |
| EV-Q02 | ToolQuality 基线 | [docs/phase0/tool-quality-baseline.md](./phase0/tool-quality-baseline.md) | 15min | [x] 2026-05-24 |
| EV-Q03 | IntentPredictor 审计 | [docs/phase0/intent-predictor-audit.md](./phase0/intent-predictor-audit.md) | 15min | [x] 2026-05-24 |
| EV-Q04 | 智商评分 rubric | [docs/phase0/iq-scoring-rubric.md](./phase0/iq-scoring-rubric.md) | 15min | [x] 2026-05-24 |
