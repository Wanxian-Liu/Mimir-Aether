# Gateway 稳定性待办（Session 78 十条）

> 来源：`data/persistent.json` → `progress.pending_tasks`（仓库副本；**真状态以代码+日志为准**）。  
> **Mimir**：复现、配置、小文档、记 ISSUES。  
> **工程/Cursor**：改 `gateway/`、`agent/` 行为或新子系统。

---

## 总表

> **状态列更新**：2026-05-24（A1 硬重启后；飞书端到端仍待刘哥复验 #9）


| #   | 摘要                | 优先级 | 状态（2026-05-24）                          | 下一步                                                                                        |
| --- | ----------------- | --- | --------------------------------------- | ------------------------------------------------------------------------------------------ |
| 1   | Watchdog 超时       | 中   | **STAB-01 已合** (2026-05-25)              | 飞书 WS 非阻塞 dispatch + AIAgent activity 心跳；**7 日**盯 watchdog.log |
| 2   | Token 失败          | 中   | 部分已验证                                   | P2-1/1b 已合；WIP 常驻后盯刷新日志                                                                    |
| 3   | Reaction 未处理      | 低   | 未复现 (2026-05-20)                        | gateway.log 无 reaction 记录；无人发过 reaction                                                    |
| 4   | Event loop closed | 低   | **STAB-02 已合** (2026-05-25)              | run_async 持久 loop；gateway 启停清理 httpx 缓存 |
| 5   | API Server 无密钥    | 高   | **已验证** (2026-05-20)                    | config.yaml 无 api_server 段；默认 127.0.0.1；非 loopback 强制 key；符合 SECURITY                      |
| 6   | fal_client 缺失     | 低   | 已说明                                     | 可选依赖；非收图主路径                                                                                |
| 7   | 孤儿 tool message   | 低   | **已验证**                                 | PR #4；05-20 日志无 `tool must be a response`                                                  |
| 8   | ToolGuard 相对路径    | 低   | **已验证** (2026-05-25)                   | STAB-03：`resolve_path_for_guard` + 越界 block + `test_tool_guard_paths` |
| 9   | 飞书卡片渲染失败          | 低   | **已验证** (2026-05-25)                   | T-03 空表头刘哥复验 pass；列名 `—`；无 230099 |
| 10  | Agent 偶发崩溃        | 高   | **栈已收集** (2026-05-20)                   | 21次 Agent error；Traceback 集中在 gateway/run.py L3593/8422；TRUNCATE 基线 19 保持                  |


---

## 分项说明

### #5 API Server 无密钥

- 读：`docs/SECURITY.md`、`gateway/platforms/api_server.py`
- Mimir：确认 bind 与 `API_SERVER_KEY`；loopback 可无 key（文档已说明）

### #10 Agent 偶发崩溃

- Mimir：导出崩溃前后 50 行 `agent.log`
- 工程：根据栈修 `agent/core_loop` 或 `gateway/run.py`

### #1 Watchdog 超时

- **STAB-01 (2026-05-25)**：`feishu_adapter` 入站非阻塞；`run_agent.AIAgent` 活动心跳 + `get_activity_summary`。
- Mimir：7 日内 `watchdog.log` 无新 timeout；长跑推理时飞书 WS 保持在线。
- 工程：若仍复现，对照 [`OPERATIONS_GATEWAY.md`](./OPERATIONS_GATEWAY.md) §4.1

### #7 孤儿 tool message

- **代码**：`main` 含 `_sanitize_tool_messages` / `_clean_orphan_tools`
- Mimir：重启 gateway 后触发工具对话，`grep "tool must"`

### #9 飞书卡片 / #2 空列名

- **代码**：`html_to_feishu_card._normalize_table_column_name`
- Mimir：发空 `<th>` HTML 表，确认 `—`

### #6 fal_client

- 日志：`Could not import tools.image_generation_tool: No module named 'fal_client'`
- Mimir：记「可选模块」；非收图主路径

### #4 Event loop closed

- **STAB-02 (2026-05-25)**：`run_agent` / `core_loop` 工具 dispatch 用 `run_async`；gateway 启停 httpx 缓存清理。
- Mimir：长跑/多轮后 `agent.log` 无 `Event loop is closed`

---

## 与 gstack P0 对照


| gstack P0       | 本表                         |
| --------------- | -------------------------- |
| 上下文截断 / 孤儿 tool | #7 + PR #4                 |
| WebSocket 断连    | #1 + Phase D（未列入 Mimir 执行） |
| 零监控             | Phase D                    |
| 自修无回滚           | **STAB-05 已合** (2026-05-25)              |
| 飞书收图            | P2-1b + P2-1c（非本表原序号）      |


---

## 完成定义

- **Mimir 阶段完成**：十条各有「已验证 / 已记 ISSUES / 已移交工程」之一，写入 `MIMIR_ISSUES.md` 或本表状态列。
- **工程阶段完成**：对应 PR + tier0 绿 + evolution_log。

