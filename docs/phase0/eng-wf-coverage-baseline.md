# ENG-WF-10: 覆盖率基线

> **真源**：[`MIMIR_ENGINEERING_WORKFLOW.md`](../MIMIR_ENGINEERING_WORKFLOW.md) §4 ENG-WF-10  
> **日期**：2026-06-01 · **Commit**：`112cfea`

---

## 基线数字

| 范围 | 行数 | 覆盖行 | 覆盖率 |
|:----:|:---:|:------:|:-----:|
| agent/ | — | — | — |
| gateway/ | — | — | — |
| tools/ | — | — | — |
| **TOTAL** | **63,356** | **50,197** | **21%** |

## 命令

```bash
./scripts/coverage_baseline.sh
```

## 失败测试

5 failed（4 个 pre-existing L2/L3 + 1 个 `test_audit_skill_usage`），与本任务无关。

## 下次对比

波次 2 收官（ENG-WF-14）时再跑一次，对比 TOTAL 变化。
