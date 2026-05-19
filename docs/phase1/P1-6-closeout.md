# Phase 1 — P1-6 关单

| 字段 | 值 |
|------|-----|
| **日期** | 2026-05-19 |

---

## 关单检查

| 步骤 | 产物 | 状态 |
|------|------|------|
| P1-1 | [`P1-1-audit-summary.md`](./P1-1-audit-summary.md) | ✅ |
| P1-2 | 补缺迁移跳过（0 缺失） | ✅ |
| P1-3 | [`P1-3-capsule-sample-audit.md`](./P1-3-capsule-sample-audit.md) | ✅ 10/10 |
| P1-4 | [`P1-4-smoke-tier0.md`](./P1-4-smoke-tier0.md) | ✅ tier0 绿 |
| P1-5 | [`MIMIR_MIMICORE_SPRING_SCOPE.md`](../MIMIR_MIMICORE_SPRING_SCOPE.md) §4.3 归档声明 | ✅ |
| P1-6 | 本文件 + backlog/issues | ✅ |

## 跟踪项更新

- [`MIMIR_EXEC_BACKLOG.md`](../MIMIR_EXEC_BACKLOG.md) **#3** → `[x]`
- [`MIMIR_ISSUES.md`](../MIMIR_ISSUES.md) **#6** → `resolved`

**说明**：`MIMIR_ISSUES.md` **#3**（三条记忆入口未统一）仍为 `open`，不在 Phase 1 胶囊迁移范围内。

## 代码附带修复（P1-4 tier0）

`MimirAgentLoop` 接入后 `budget._used` 未同步，导致 `test_turn_loop_budget` 失败；已在 `agent/core_loop.py` 在 `_loop.run()` 后按 `turns_used` 调用 `budget.consume()`。
