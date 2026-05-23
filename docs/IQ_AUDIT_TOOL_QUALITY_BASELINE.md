# ToolQualityManager 基线快照

**日期**：2026-05-21  
**来源**：EV-Q02（琬弦智商方案方向四 — 工具智能 P1）

> **ToolQuality 真源（2026-05-24）** → [`docs/phase0/tool-quality-baseline.md`](./phase0/tool-quality-baseline.md)（含 DB 快照 TOP10）。下文为历史框架。

## 实际状态

| 维度 | 内容 |
|------|------|
| **模块** | `agent/tool_quality.py` — 314 行 |
| **存在？** | ✅ 存在，非空壳 |
| **存储** | SQLite `~/.mimiraether/data/tool_quality.db` |
| **数据结构** | `ExecutionRecord` (timestamp/success/duration_ms/error_message) + `ToolQualityRecord` (tool_key/tool_name/recent_executions) |
| **窗口** | 最近 20 次执行（滚动窗口） |
| **质量排名** | 结合成功率和最近失败惩罚的评分 |
| **演进触发** | 每 N 次全局执行触发一次进化检查 |

## 当前基线（数据快照待采集）

> ⚠️ 需要运行工具查询实际 tool_quality.db 获取数字。以下为框架：

| 工具名称 | 总调用 | 成功率 | 平均延迟(ms) | 最近失败原因 |
|---------|:--:|:--:|:--:|------|
| `read_file` | ? | ?% | ? | — |
| `search_files` | ? | ?% | ? | — |
| `patch` | ? | ?% | ? | — |
| `terminal` | ? | ?% | ? | — |
| `write_file` | ? | ?% | ? | — |
| `session_search` | ? | ?% | ? | — |
| `produce_capsule` | ? | ?% | ? | GDI 评分未达标 |
| `send_message` | ? | ?% | ? | — |
| `web_search` | ? | ?% | ? | — |
| `web_extract` | ? | ?% | ? | — |

## 查询方法（待运行）

```bash
sqlite3 ~/.mimiraether/data/tool_quality.db "
SELECT tool_name, 
       COUNT(*) as total,
       ROUND(100.0*SUM(CASE WHEN success THEN 1 ELSE 0 END)/COUNT(*),1) as success_rate,
       ROUND(AVG(duration_ms),0) as avg_latency_ms
FROM executions 
WHERE timestamp > datetime('now','-30 days')
GROUP BY tool_name 
ORDER BY total DESC
LIMIT 15;
"
```

## 对 ToolPromptOptimizer 的意义

ToolQualityManager **已有数据和评分机制**。方案方向二的 ToolPromptOptimizer 可以直接复用其数据：高频低成功率 → 详细示例，高频高成功率 → 压缩 prompt。

## 结论

**ToolQualityManager 非空壳**（314 行真实代码 + SQLite 持久化）。基线数字需查询 DB 后补充。
