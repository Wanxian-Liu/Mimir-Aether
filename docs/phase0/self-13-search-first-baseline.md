# SELF-13: Search-First 审计基线

> Generated: 2026-06-01T08:48Z
> 范围: 全部历史会话 JSONL（抽样 20 条 / filtered 20 条）

---

## 基线数据

| 指标 | 值 |
|------|----|
| 总 recall 候选 | 640 |
| 过滤后 recall 候选 | 115 |
| **过滤后违规率** | **100% (20/20)** |
| 违规模式 | `no session_search before next user turn` |

## 根因

| 因子 | 说明 |
|------|------|
| **SELF-11 未部署** | `agent/agent_loop.py` 的 preemptive 搜索已 commit/push 但尚未部署（需刘哥重启 Gateway） |
| **历史会话** | 全部违规来自旧会话，检测时无程序化搜索 |
| **排除合理** | 640→115 过滤后排除 bridge_write_task、broad_recall_not_explicit 等 FP |

## 建议

1. **Gateway 重启后再次审计**：刘哥重启后运行 `python3 scripts/search_first_audit.py --limit 10`，预期 `filtered_violation_rate` 下降
2. **长期**：SELF-11 + SELF-12（nudge contract 测试 28 项）形成完整的 search-first 契约覆盖
3. **SELF-17 closeout** 时将本基线作为 M4/M5 指标

## 审计脚本增强（本粒产出）

- 新增 `_PREEMPTIVE_MARKER = "[preemptive-search]"` 常量
- 审计内层循环跳过 preemptive 消息（与 guard 消息同等对待）
- 识别 preemptive 消息作为有效的 search-first 证据（`evidence = "preemptive session_search"`）
- 修复 `TOOL_CALL_RE` regex 转义错误
