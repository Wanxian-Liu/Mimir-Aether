# EV-A04 — 架构评分 rubric（2026-05-24）

> 刷新 [ARCHITECTURE_SCORING_RUBRIC.md](../ARCHITECTURE_SCORING_RUBRIC.md)；依据 phase0 A01/Q 与 tier0 **237+2**。

## 摘要

- **加权 6.1/10**（2026-05-21 **5.5**；方案自评 7.8 仍偏高）。
- 提升：**职责**（core→`MimirAgentLoop` 委托）、**可测试性**（`tests/agent` E-006–E-012）。
- 仍弱：**耦合**（`router_mixin` 3573 行）、**硬编码**（[Q01](./hardcoded-thresholds.md) 23 项）。

## 7 维评分

| 子维度 | 权 | 现评 | 目标 | 依据 |
|--------|:--:|:--:|:--:|------|
| 职责清晰度 | 25% | 6.0 | 8.0 | [A01](./agent-core-responsibility-map.md) 委托清晰；prompt 仍含 guard |
| 耦合度 | 20% | 5.5 | 7.5 | gateway↔agent 单向 import 为主；GOD 文件仍集中 |
| 可测试性 | 15% | 5.5 | 7.0 | tier0 237+2；`tests/agent` 集成增；覆盖率仍低 |
| 可替换性 | 15% | 6.0 | 8.0 | `tools.registry`、LLM port；M5 切片 |
| 启动/性能 | 10% | 7.0 | 8.0 | mimicore 延迟/路径注入；gateway ~10s |
| 配置化 | 10% | 6.0 | 7.5 | `.env` + yaml；阈值多硬编码 |
| 文档完整度 | 5% | 8.5 | 9.0 | phase0 真源链 + ADR/path-contract |

## 加权

`6.0×0.25 + 5.5×0.20 + 5.5×0.15 + 6.0×0.15 + 7.0×0.10 + 6.0×0.10 + 8.5×0.05` = **6.1/10**

## vs 2026-05-21

| 项 | 旧 | 新 |
|----|----|-----|
| 总分 | 5.5 | **6.1** |
| core_loop | ~2000 双循环 | **1295** 配置层 + **565** 执行层 |
| tier0 | 181+2 | **237+2** |
| 可测试性依据 | 「无 agent_loop 集成」 | EP-C / E-012 / intent-action 测 |

**Phase 1**：P0 orchestrator（adapter 抽离）；P1 `agent/guard`（→ A05）；A03 Memory 后再评耦合/可替换性。
