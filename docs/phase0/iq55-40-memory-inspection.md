# IQ55-40 — 记忆上限巡检报告（2026-06-02）

> **任务**：检查 memory 总量是否接近 55k 上限，评估精简策略
> **等级**：8.5（实际为一次速查，5 分钟完成）

---

## 结论

🏁 **远低于上限。无需紧急行动。**

## 核心数据

| 指标 | 值 | 阈值 | 状态 |
|------|----|------|------|
| `persistent.json` 大小 | **18.2 KB** | ~55 KB | ✅ 仅 33%，头枕 66%（36KB） |
| memory 段 | **6.3 KB**（5 条） | — | ✅ 极小 |
| user 段 | **2 chars**（空） | — | ✅ 未使用 |
| session_count | **202** | — | ✅ 正常 |

## 可精简项（非阻塞）

| 条目 | 数量 | 建议 |
|------|------|------|
| `key_decisions` | **21** 条 | prompt 只注入最近 5 条（已实现）；持久可保留全量 |
| `learned_patterns` | **11** 条 | prompt 只注入最近 3 条（已实现）；持久可保留全量 |
| `active_projects` | **16** 条 | prompt 按状态/时间过滤；已实现 |
| `skills_used` | 空 list | 无 |

## 现有护栏（已实现）

| 机制 | 位置 | 行为 |
|------|------|------|
| `MIMIR_CROSS_SESSION_MAX_CHARS` | `agent/prompt_builder.py` | 默认 2000 chars cap |
| `_cross_session_list_limit` | `agent/prompt_builder.py` | 按源限制注入数量 |
| `_build_cross_session_context` | `agent/prompt_builder.py` | 超长截断 |

## 精简策略（如果需要加速清理）

```markdown
1. `key_decisions` 保留最近 16 条最相关（支持 `stale` 标记过期）
2. `learned_patterns` 保留最近 8 条，合并相似
3. `active_projects` 完成项目标记 `completed`，然后过滤显示
4. **不自动删除** — 让刘哥决定保留策略
```

## 建议

- **现在不需要做任何事** — 18KB/55KB 头枕充足
- **巡检频率**：每 100 session 或文件 >40KB 时重检
- **下次关注时机**：session_count > 600 或 persistent >40KB
