# Gateway 稳定性待办（Session 78 十条）

> 来源：`data/persistent.json` → `progress.pending_tasks`（仓库副本；**真状态以代码+日志为准**）。  
> **Mimir**：复现、配置、小文档、记 ISSUES。  
> **工程/Cursor**：改 `gateway/`、`agent/` 行为或新子系统。

---

## 总表

> **状态列更新**：2026-05-27（**MI-AWAY-12**）


| #   | 摘要                | 优先级 | 状态（2026-05-25）                          | 备注 |
| --- | ----------------- | --- | --------------------------------------- | ---- |
| 1   | Watchdog 超时       | 中   | **STAB-01 已合** · Mimir 7 日观察          | 飞书 WS 非阻塞 + activity 心跳；见 `OPERATIONS_GATEWAY.md` §4.1 |
| 2   | Token 失败          | 中   | **已验证**                                 | P2-1/1b token 刷新 + message-resource；常驻后盯 refresher 日志 |
| 3   | Reaction 未处理      | 低   | **已验证** (未复现)                         | gateway.log 无 reaction；无人发过 reaction |
| 4   | Event loop closed | 低   | **STAB-02 已合**                           | `run_async` 持久 loop；gateway 启停 httpx 缓存清理 |
| 5   | API Server 无密钥    | 高   | **已验证** (2026-05-20)                    | loopback 默认；非 loopback 强制 key — `SECURITY.md` |
| 6   | fal_client 缺失     | 低   | **已说明**                                 | 可选依赖；非收图主路径 |
| 7   | 孤儿 tool message   | 低   | **已验证**                                 | PR #4；日志无 `tool must be a response` |
| 8   | ToolGuard 相对路径    | 低   | **STAB-03 已合**                           | `resolve_path_for_guard` + `test_tool_guard_paths` |
| 9   | 飞书卡片渲染失败          | 低   | **已验证** (2026-05-25)                   | T-03 刘哥复验 pass；列名 `—` |
| 10  | Agent 偶发崩溃        | 高   | **STAB-04 已合** · monitoring              | 双 TRUNCATE 已修；since-start TRUNCATE=0；余债见 `MIMIR_ISSUES.md` #10 |


---

## STAB 结案映射（GH #25–30）

| GH | Gateway # | STAB | 工程 commit | 状态 |
|----|-----------|------|-------------|------|
| #25 | WS 心跳 | STAB-01/06 | `98a6f6d` | closed |
| #26 | 自修回滚 | STAB-05 | `7b6dfdc` | closed |
| #27 | Watchdog | STAB-01 | `98a6f6d` | closed（7 日观察 Mimir） |
| #28 | Event loop | STAB-02 | `edba235` | closed |
| #29 | ToolGuard | STAB-03 | `1101648` | closed |
| #30 | Agent 崩溃/TRUNCATE | STAB-04 | `03b9102` 等 | closed（非 TRUNCATE 余债 monitoring） |

---

## 分项说明

### #5 API Server 无密钥

- 读：`docs/SECURITY.md`、`gateway/platforms/api_server.py`
- Mimir：确认 bind 与 `API_SERVER_KEY`；loopback 可无 key（文档已说明）

### #10 Agent 偶发崩溃

- **STAB-04**：双 TRUNCATE、`recovery` code-error 分流、gateway drain guard
- Ops：`mimir_health_check.sh` R4 since-start；#10 **documented exception**（[`obs-b1-03-issue10-closeout.md`](./phase0/obs-b1-03-issue10-closeout.md)）

### #1 Watchdog 超时

- **STAB-01**：`feishu_adapter` 非阻塞 dispatch；`run_agent.AIAgent` activity 心跳
- Mimir：7 日内 `watchdog.log` 无新 timeout

### #7 孤儿 tool message

- **代码**：`_sanitize_tool_messages` / `_clean_orphan_tools`
- Mimir：工具对话后 `grep "tool must"` 应为空

### #9 飞书卡片 / #2 空列名

- **代码**：`html_to_feishu_card._normalize_table_column_name`
- Mimir：空 `<th>` → 列名 `—`

### #6 fal_client

- 可选模块；非收图主路径

### #4 Event loop closed

- **STAB-02**：`run_async` + gateway httpx 启停清理
- Mimir：`agent.log` 无新 `Event loop is closed`

### #5 自修回滚（稳定性基建，非十条序号）

- **STAB-05**：`evolution_rollback` + `data/evolution_backups/` — 见 `OPERATIONS_GATEWAY.md` §4.1

---

## 与网关稳定性 P0 对照


| 稳定性基建 P0   | 本表                         |
| --------------- | -------------------------- |
| 上下文截断 / 孤儿 tool | #7 + PR #4 + STAB-04       |
| WebSocket 断连    | #1 STAB-01/06              |
| 零监控             | Phase D / icebox #22       |
| 自修无回滚           | STAB-05                    |
| 飞书收图            | P2-1b + P2-1c              |


---

## 完成定义

- **Mimir 阶段完成**：十条各有「已验证 / 已记 ISSUES / 已合工程」之一 — **STAB-07 ✅**
- **工程阶段完成**：STAB-01～07 PR + tier0 绿 + evolution_log — **STAB-07 ✅**
