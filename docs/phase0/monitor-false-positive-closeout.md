# SELF-08：Monitor 真/假阳性 Closeout

> Generated: 2026-06-01 · Source: `data/monitor_alerts.json`

---

## 分类结果

| 类型 | 数量 | 占比 |
|------|------|------|
| **假阳性（已知）** | 96 | **97.0%** |
| **真阳性（真实）** | 3 | **3.0%** |
| 总计 | 99 | 100% |

### 假阳性明细（96 条）

| 工具 | 错误 | 性质 | 建议 |
|------|------|------|------|
| `crash_tool` | 48× "Simulated crash" | 设计使然——故意崩溃工具，`quality_score=0.0` | 从监控排除 |
| `orphan_tool` | 48× "Tool handler not implemented" | 未实现占位工具，`quality_score=0.0` | 从监控排除 |

### 真阳性明细（3 条）

| # | 工具 | 错误 | 状态 |
|---|------|------|------|
| 1 | `terminal` | 命令超时被 BLOCKED | ⚠️ 正常行为——超时 gate 工作正常 |
| 2 | `execute_code` | sandbox 中执行 bash 命令语法错误 | ✅ 已修复——用户错误，非代码问题 |
| 3 | `skill_view` | "Skill not found: mimiraether-self-audit" | **✅ 已修复**——SELF-05 创建了该技能 |

## 结论

**无需生产修复。** 97% 告警是 `crash_tool`/`orphan_tool` 假阳性（`quality_score=0.0` 已知问题，非回归）。剩余 3 条真阳性均已在现有 SELF 链中处理（SELF-05 创建技能、超时 gate 设计特性）。

## 建议

1. 在监控聚合管道中**排除** `crash_tool` + `orphan_tool`
2. 聚焦 `read_file`/`terminal`/`search_files`/`patch`/`execute_code` 的真实错误率
3. 周常 `brain_metrics_snapshot.py` 已覆盖 top 5 工具成功率的真实监控
