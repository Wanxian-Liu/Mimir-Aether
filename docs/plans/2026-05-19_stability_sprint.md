# 稳定性冲刺计划（2026-05-19）

> **你出门期间**：Cursor 已落地代码 + 文档；**Mimir** 按 `docs/MIMIR_EXEC_BACKLOG.md` §Mimir 可执行 逐项冒烟与回报。  
> **不要**改架构的项留在 §需设计/工程；**勿**提交 `data/persistent.json`（runtime 镜像，易假闭合）。

---

## 0. 今日已落地（代码在 `main`，本地领先 origin 2 commit）

| ID | 内容 | commit |
|----|------|--------|
| P2-1b | 飞书入站图 → `message-resource` API | `43cbd3a` |
| P2-1c | Vision：`deepseek-chat` 等纯文本模型 → 回退 OpenRouter/Nous | `b50c71c` |
| — | PR #4/#5 已合并到 main（`6fbcc8f`、`23583a9`） | remote |
| — | `gateway/status.py` 去除 openclaw 进程名 | `43cbd3a` |

**验证证据（刘哥已提供）**：`2026-05-19 13:56:20 Image downloaded`（message-resource 成功）。

**仍待验证**：重启 gateway 加载 `b50c71c` 后，vision 不再出现 `unknown variant image_url`。

---

## 1. 阶段划分

```mermaid
flowchart LR
  A[Phase A 冒烟] --> B[Phase B 文档收口]
  B --> C[Phase C Gateway 债]
  C --> D[Phase D 架构项排队]
```

### Phase A — Mimir 冒烟（无改代码，~30min）

| # | 任务 | 成功标准 |
|---|------|----------|
| A1 | `gateway restart`（加载最新 main） | `feishu connected` |
| A2 | 飞书发图 | 日志：`Image downloaded` + vision 无 `image_url` 400；Mimir 能描述图 |
| A3 | 飞书发含空 `<th>` 表 | 列名 `—`，非纯文本回退 |
| A4 | 飞书发一条触发 tool 的消息 | 无 `tool must be a response` |
| A5 | 确认 `OPENROUTER_API_KEY`（vision 回退） | `.env` 有 key 或 config 指定 vision provider |

回报模板见 `docs/MIMIR_EXEC_BACKLOG.md` §回报模板。

### Phase B — 文档（Mimir 或 Cursor）

| # | 任务 | 负责人 |
|---|------|--------|
| B1 | `ISSUES.md` #1 下载→resolved；#1 识图→resolved（A2 通过后） | Mimir |
| B2 | `ISSUES.md` #2→resolved（A3 通过后） | Mimir |
| B3 | `git push origin main`（含 43cbd3a、b50c71c） | 刘哥或 Mimir（需授权） |
| B4 | M6：`record_m6_evolution.sh` 两行（P2-1b + vision 回退） | Cursor 已可补 |

### Phase C — Gateway 10 项（见 `docs/GATEWAY_STABILITY_BACKLOG.md`）

按 **Mimir 可做 / 需工程** 分列；Mimir 只做「配置检查 + 复现 + 记 ISSUES」，不擅自改 `gateway/run.py` 大逻辑。

### Phase D — 需设计（不进 Mimir 执行清单）

| 项 | 原因 |
|----|------|
| WebSocket 推理阻塞心跳 | 需改 adapter/loop 架构 |
| 零监控 / 告警 | 新组件或外部集成 |
| 自修无回滚护栏 | 策略 + 实现 |
| P3-0 persistent 单写 ADR | 架构约定 |
| P4-1 memory 三入口统一 | 路径与产品面 |

---

## 2. 风险与依赖

- **Vision 回退**依赖 OpenRouter 或 Nous 凭证；无 key 时 A2 仍会失败。
- **Gateway 双实例**：`cli.py gateway restart` 可能杀不掉旧 PID；用手动 `kill` + `gateway.pid`（见会话记录）。
- **persistent.json**：仓库内 `data/persistent.json` 的 ✅ 与代码不同步时，以 **grep/日志** 为准，不以 JSON 为准。

---

## 3. Cursor 离线已完成（2026-05-19）

- [x] 计划本文档
- [x] `docs/GATEWAY_STABILITY_BACKLOG.md`
- [x] `docs/MIMIR_EXEC_BACKLOG.md` §Mimir 可执行
- [x] `docs/MAINLINE_STATUS.md` 快照更新
- [x] `docs/phase2/P2-1-feishu-image.md` 补充 vision 说明
- [x] tier0 PASS（`b50c71c` 后）

---

## 4. 回来后刘哥只看这三处

1. `docs/MIMIR_EXEC_BACKLOG.md` — Mimir 勾选项  
2. `~/.mimiraether/logs/agent.log` — A2 grep  
3. `git log origin/main..main` — 是否已 push  
