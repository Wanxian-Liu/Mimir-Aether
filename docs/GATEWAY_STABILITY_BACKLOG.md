# Gateway 稳定性待办（Session 78 十条）

> 来源：`data/persistent.json` → `progress.pending_tasks`（仓库副本；**真状态以代码+日志为准**）。  
> **Mimir**：复现、配置、小文档、记 ISSUES。  
> **工程/Cursor**：改 `gateway/`、`agent/` 行为或新子系统。

---

## 总表

> **状态列更新**：2026-05-24（A1 硬重启后；飞书端到端仍待刘哥复验 #9）

| # | 摘要 | 优先级 | 状态（2026-05-24） | 下一步 |
|---|------|--------|-------------------|--------|
| 1 | Watchdog 超时 | 中 | 移交工程 | 与 WebSocket/长跑推理同源排查 |
| 2 | Token 失败 | 中 | 部分已验证 | P2-1/1b 已合；WIP 常驻后盯刷新日志 |
| 3 | Reaction 未处理 | 低 | 未复现 (2026-05-20) | gateway.log 无 reaction 记录；无人发过 reaction |
| 4 | Event loop closed | 低 | 移交工程 | async 生命周期 |
| 5 | API Server 无密钥 | 高 | **已验证** (2026-05-20) | config.yaml 无 api_server 段；默认 127.0.0.1；非 loopback 强制 key；符合 SECURITY |
| 6 | fal_client 缺失 | 低 | 已说明 | 可选依赖；非收图主路径 |
| 7 | 孤儿 tool message | 低 | **已验证** | PR #4；05-20 日志无 `tool must be a response` |
| 8 | ToolGuard 相对路径 | 低 | 待复现 | 工程 path 修复 |
| 9 | 飞书卡片渲染失败 | 低 | 代码已合·**Gateway 已重启**·待飞书复验 (2026-05-24) | PR #5 空 `<th>`→`—`；`restart_gateway_hard.sh` → PID 691521；刘哥按 `mimir_prod_smoke.md` §A1 复验 |
| 10 | Agent 偶发崩溃 | 高 | **栈已收集** (2026-05-20) | 21次 Agent error；Traceback 集中在 gateway/run.py L3593/8422；TRUNCATE 基线 19 保持 |

---

## 分项说明

### #5 API Server 无密钥

- 读：`docs/SECURITY.md`、`gateway/platforms/api_server.py`
- Mimir：确认 bind 与 `API_SERVER_KEY`；loopback 可无 key（文档已说明）

### #10 Agent 偶发崩溃

- Mimir：导出崩溃前后 50 行 `agent.log`
- 工程：根据栈修 `agent/core_loop` 或 `gateway/run.py`

### #1 Watchdog 超时

- Mimir：记录超时发生时的 gateway 负载、是否在长跑推理
- 工程：与 **P0 WebSocket/心跳** 可能同源（见 stability sprint Phase D）

### #7 孤儿 tool message

- **代码**：`main` 含 `_sanitize_tool_messages` / `_clean_orphan_tools`
- Mimir：重启 gateway 后触发工具对话，`grep "tool must"`

### #9 飞书卡片 / #2 空列名

- **代码**：`html_to_feishu_card._normalize_table_column_name`
- Mimir：发空 `<th>` HTML 表，确认 `—`

### #6 fal_client

- 日志：`Could not import tools.image_generation_tool: No module named 'fal_client'`
- Mimir：记「可选模块」；非收图主路径

---

## 与 gstack P0 对照

| gstack P0 | 本表 |
|-----------|------|
| 上下文截断 / 孤儿 tool | #7 + PR #4 |
| WebSocket 断连 | #1 + Phase D（未列入 Mimir 执行） |
| 零监控 | Phase D |
| 自修无回滚 | Phase D |
| 飞书收图 | P2-1b + P2-1c（非本表原序号） |

---

## 完成定义

- **Mimir 阶段完成**：十条各有「已验证 / 已记 ISSUES / 已移交工程」之一，写入 `MIMIR_ISSUES.md` 或本表状态列。
- **工程阶段完成**：对应 PR + tier0 绿 + evolution_log。
