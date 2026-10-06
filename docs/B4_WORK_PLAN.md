# B4 / B4b · 实施骨架（半段 · 按 B3 规则①自身要求：先落盘再补证）

> 派单：Hermes（四方件 · B3 已加载后的续队）· 前置：B3 防截断 = commit `b279c90`（20:18:08），外部重启 PID 2344557（22:54:24）> 提交 ⇒ **B3 已加载**。
> 交付纪律（派单原文）：**一件一提交一证据，完一件立刻交一件回执**（每件一次 buzz/fb·不合并）；禁 `git add -A`；commit message 末行 `Agent: mimir`；回执 ≤200 行。
> 队列原文：**B4**（run 级空跑计数出声）· **B4b**（启动钩子接 `resume_pending_indexes()`，**不接 cron**）。

## 1. 已确证读数（本轮盘上取证）

| 读数 | 命令 | 实测 |
|---|---|---|
| 空跑闸门体量 | `wc -l agent/empty_run_gate.py` | 402 |
| 轮次循环体量 | `wc -l agent/agent_loop.py` | 1991 |
| 续传函数定义 | `grep -n 'def resume_pending_indexes' tools/session_search_indexer.py` | `:432` |
| pending 报告定义 | `grep -n 'def pending_index_report' tools/session_search_indexer.py` | `:371` |
| 既有续传入口 | `scripts/resume_index.py` | `:48` 调 `resume_pending_indexes(like_db=db, limit=…)`（rc 0=无 pending / 1=仍有） |
| 空跑闸门 env | `grep -n 'MIMIR_EMPTY_RUN' agent/empty_run_gate.py` | `MIMIR_EMPTY_RUN_GATE`（`:69`）· `MIMIR_EMPTY_RUN_MAX_FORCE`（`:81`，默认 2） |

> 注：`write_file`/`patch` 对本仓（project dir）判只读 ⇒ 本文件经 `execute_code` 落盘（工具面既有限制，非绕行）。

## 2. 待补清单（未闭项 · 逐条关闭后追加）

- [ ] T1 定 **B4 语义边界**：run 级空跑「计数」记在哪（run 内累积位，非 turn 级 `_has_written_this_turn`）· 「出声」落到哪个既有出口（日志字段 / 收尾 reason / 台账）。
- [ ] T2 定 **挂点**：复用既有范式（`empty_run_gate` 的 in-loop tick + pre-exit flush）还是收尾路径——**倾向复用，不另造**。
- [ ] T3 B4 受控差分单测（有落盘 vs 零落盘两臂；禁形容词判据）。
- [ ] T4 B4b **启动钩子挂点**：gateway 启动路径中的钩子位置（`gateway/run.py` 或 agent 初始化）· 明确**不接 cron**、不新增 unit。
- [ ] T5 B4b 幂等与失败降级：pending 索引续传失败不得阻断启动（fail-open）· 幂等键。
- [ ] T6 B4b 受控差分单测（有 pending / 无 pending 两臂）。

## 3. 边界声明（预登记）

- 允许动：`agent/empty_run_gate.py`（如需）· 启动钩子所在文件 · `tests/` · 本文件。
- **不动**：`~/.openclaw/**`、`~/.hermes/**`（除回执）、`cron/jobs.json`、真记忆面（`memories/**`、`data/persistent.json`）。
- **不自重启**；不接 cron。

---
*本文件 = 半段（骨架先行）。续写**追加**，不重写。*


## 4. B4 实施结果（2026-10-06 本 run）

**形态**：`agent/run_health.py`（新 · 229 行 · 观测层，不改判定）+ `agent/core_loop.py` 收尾路径一处调用（`_exit_reason` 解析后，B3 半段兜底之前）。

| 落点 | 文件 | 内容 |
|---|---|---|
| 计数台账 | `~/.mimiraether/logs/run_health.jsonl` | 每 run 一行（ts/date/exit_reason/turns_used/max_turns/task_id/session_id/content_len）· append-only |
| 计数逻辑（pure） | `run_health.daily_counts()` | 按日过滤 + 静默死族聚合（`empty_content`/`max_turns`/`verify_exhausted`/`circuit_breaker`）· 坏行跳过 |
| 阈值判据（pure） | `run_health.evaluate()` | 越线理由串（空 = 未越线）；`limit=0` ⇒ 该类关闭 |
| 出声 | `logger.error("[RUN_HEALTH_ALERT] …")` + `data/ops/run_health_alerts.jsonl` | gateway.log 可 grep + 告警台账 |
| 状态快照 | `data/ops/run_health_state.json` | 当日计数 + `alerted` 幂等标记 ⇒ 外部巡视**读文件即可**，不必 grep 日志 |
| 挂点 | `agent/core_loop.py` `_exit_reason` 之后 | fail-open（异常只降级一行 warning，不打断收尾） |

**阈值（env 可调）**：`MIMIR_RUN_HEALTH_EMPTY_THRESHOLD`=2 · `MIMIR_RUN_HEALTH_MAXTURNS_THRESHOLD`=1 · 回滚 `MIMIR_RUN_HEALTH=0`。
**幂等**：同类告警每自然日只出声一次（计数照旧逐 run 累加）。

**设计取舍（受控差分挡下一次真问题）**：初版把 `silent_death` 总数（默认 ≥3）也当出声类 ⇒ 3 次 `empty_content` 会**同时**触发 `empty_content` 与 `silent_death` 两条（**同一事实两声**）。测试 `test_threshold_env_override_suppresses_alert` 当场红 ⇒ 改为：`silent_death` **只进计数**（state/ledger 供外部读），**出声面严格等于任务书点名的两类**。

**受控差分读数**（`bash scripts/pytest_isolated.sh tests/agent/test_run_health.py -q`）：差分维度 = 日期 / 阈值 / 阈值 env / 连续 run 次数 / 路径可写性；判据全为数字（计数、fired 列表、告警条数）。
- B4 单测：**11 passed**（含接线守卫：core_loop 真调 `record_run_exit(_exit_reason,…)`——防「闸门在、调用点被摘」的恒假族）
- 回归：B4 11 + B3 16 + B1/B2 20 = **52 passed**（`tests/agent/test_run_health.py tests/test_b3_production_checkpoint.py tests/test_output_budget_retry.py`）

---

*追加段（未重写 §1–§3）。*


## 5. B4b 实施结果（2026-10-06 本 run）

**形态**：**不新建文件、不接 cron**——实现落在既有索引模块 `tools/session_search_indexer.py`（同域、同真源），`gateway/run.py` **只加一处调用**（任务书「例外：只加一处调用，别扩面」）。手动入口 `scripts/resume_index.py` **原样保留**。

| 落点 | 位置 | 内容 |
|---|---|---|
| 核心逻辑（可离线测） | `session_search_indexer.startup_resume_pending(limit=…)` | pending 空 ⇒ **早退**（不建 DB 连接、不加载 embedding）；有 ⇒ 以 `like_db` 调 `resume_pending_indexes`，回报 `pending_seen` / `pending_after` / 错误 |
| 入口（env 门控 + daemon 线程） | `session_search_indexer.start_pending_index_resume_thread(logger=…)` | 延迟默认 20s、失败静默降级、线程名 `pending-index-resume` |
| 启动接线 | `gateway/run.py`（语义预热线程之后） | 一处调用 + try/except（自愈设施不得拖垮启动） |

**参数（env）**：`MIMIR_PENDING_INDEX_RESUME`（默认 1，`0` 关断）· `MIMIR_PENDING_INDEX_RESUME_DELAY_S`（默认 20）· `MIMIR_PENDING_INDEX_RESUME_LIMIT`（默认 **20**，`<=0` ⇒ 无界）。
**限流理由（内存纪律 · 非保守癖）**：本进程 cgroup 上限 4G，chroma + bge-m3 同开曾致整机 OOM（2026-10-05 事故：gateway 顶格 4.27G 时起吃 2.8G 的回填 unit）⇒ 启动回填**必须有界**，余量交下次启动/手动入口续。

**受控差分读数**（`bash scripts/pytest_isolated.sh tests/gateway/test_pending_index_startup_hook.py -q`）：差分维度 = 有无 pending / DB 构造成败 / 续传抛错 / limit env 三态（20 · 0 · 坏值）/ 钩子开关；判据 = 返回体字段 + `_FakeDB.calls` 计数 + 线程属性。
- B4b 单测：**10 passed**（含接线守卫：`gateway/run.py` 真调 `start_pending_index_resume_thread`）
- 回归（本文件 + `tests/tools/` + B4 + B3 + B1/B2）：**216 passed**
- **现场 e2e（真调用 · 非替身）**：`startup_resume_pending()` ⇒ `{"limit": 20, "pending_seen": 0, "skipped": "no_pending"}`；线程钩子（delay=0）返回 daemon=True、`is_alive()=False`、日志 `[PENDING_INDEX_RESUME] {…no_pending}`。探针：`~/.mimiraether/tmp/b4b_probe_hook.py`

---

*追加段（未重写 §1–§4）。*
