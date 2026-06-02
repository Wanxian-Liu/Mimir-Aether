# IQ-55 路线图（5.5 底线 → 9.0 Hermes 基线）

> **真源队列**：[`MIMIR_TASK_QUEUE.md`](./MIMIR_TASK_QUEUE.md) **§14**  
> **执行循环**：[`MIMIR_IQ55_EXECUTION_WORKFLOW.md`](./MIMIR_IQ55_EXECUTION_WORKFLOW.md) · `./scripts/mimir_iq55_run_next.sh`  
> **诊断勘误**：[`phase0/iq55-truth-refresh.md`](./phase0/iq55-truth-refresh.md)  
> **基线快照**：[`phase0/iq55-baseline.md`](./phase0/iq55-baseline.md)

## 等级门槛（刘哥 / Mimir 共识）

| 等级 | 条件 | 对应 §14 粒 |
|:----:|------|-------------|
| **5.5** | P0.1≤40% + P0.2 真实进化 + P1.1 intent 生产证据 | IQ55-10～12, IQ55-20 |
| **6.5** | 5.5 + 元认知复盘 **10+/周** | IQ55-30 |
| **7.5** | 6.5 + 工具 P95<10s + 模型路由 | IQ55-40, IQ55-50 |
| **8.5** | 7.5 + 跨会话意图 1 轮 + 记忆精简 | IQ55-60, IQ55-61 |
| **9.0** | Parity 证据 + 上表全绿 | `ralph_parity_contract` + MAINLINE |

**眼下只吹牛到 5.5 有数据支撑为止。**

---

## 波次 0 — 真源与基线（Cursor 或 Mimir · 无大块代码）

| ID | 任务 | Owner | 验收 |
|----|------|-------|------|
| **IQ55-00** | 刷新 `iq17-closeout` / bridge 脚注（handoff 已合） | Cursor/Mimir | 文档无「待合入」 |
| **IQ55-01** | 写 `iq55-baseline.md`：tier0、search audit、ledger、brain_metrics | Mimir | 文件含日期+数字 |
| **IQ55-02** | `python3 scripts/search_first_audit.py` → 记入 baseline | Mimir | violation_rate 可查 |
| **IQ55-03** | `python3 scripts/brain_metrics_snapshot.py` → ops 快照 | Mimir | `data/ops/brain-metrics-latest.json` 更新 |

---

## 波次 1 — 刘哥运维（已授权 · shell）

| ID | 任务 | Owner | 验收 |
|----|------|-------|------|
| **IQ55-OPS-01** | `MIMIR_WM_PREDICTOR=1` + `ensure_single_gateway.sh` | **刘哥/Cursor** | health OK · log `wm_prediction` |
| **IQ55-OPS-02** | （选开）`MIMIR_PARALLEL_TOOLS=1` 观察 1 轮飞书多工具 | 刘哥 | log `parallel dispatch` |
| **IQ55-OPS-03** | （选开）`MIMIR_NUDGE_INTERVAL=3` 长会话 | 刘哥 | log `interval nudge` ≤1/会话 |
| **IQ55-OPS-04** | 7d 后复跑 IQ55-02/03，写 `iq55-ops-closeout.md` | Mimir | WM/intent 计数非零 |

详见 [`phase0/mw-prod-env-all.md`](./phase0/mw-prod-env-all.md)。

---

## 波次 2 — P0（阻塞 5.5）

### IQ55-10 — 搜索违规率 80%→40%（P0.1）

| 子粒 | 做什么 | 验证 |
|------|--------|------|
| **IQ55-10a** | 审计：哪些 user 类绕过 guard（续跑/「还记得」/无 tool） | `search_first_audit` 分桶 JSON |
| **IQ55-10b** | 加强 `search_first_guard`：finish 前 **硬 block** 或强制 `session_search` tool_call | tier0 + `test_search_first_guard` |
| **IQ55-10c** | 与 preemptive nudge 去重（fabrication 测例不回归） | `test_eng_wf_fabrication_guard` |
| **IQ55-10d** | 周脚本：`scripts/iq55_search_weekly.sh` 写 `data/ops/search-first-weekly.json` | SELF-LOOP 可读 |
| **IQ55-10e** | closeout：`iq55-p01-search-closeout.md` **filtered≤40%** | audit JSON 为证 |

### IQ55-11 — 进化管道真实执行（P0.2）

| 子粒 | 做什么 | 验证 |
|------|--------|------|
| **IQ55-11a** | 文档化：`outcome=planned` = IC 通过但未 apply（`engine.py:227`） | ADR 或 phase0 一页 |
| **IQ55-11b** | `MIMIR_AUTO_EVOLVE=1` 时：safe_files **实际写盘** + ledger `outcome=applied` | 账本字段 + git 禁止（sandbox 路径） |
| **IQ55-11c** | 失败/回滚写 `outcome=rolled_back` | ledger 可读 |
| **IQ55-11d** | `evolution ok%` 与 ledger **同源**（禁止空指标） | brain_metrics + ledger 一致 |
| **IQ55-11e** | closeout：`iq55-p02-evolution-closeout.md` ≥1 applied | `evolution_ledger.json` |

### IQ55-12 — 工具延迟画像（P0.3 · 5.5 仅需画像，7.5 要 P95<10s）

| 子粒 | 做什么 | 验证 |
|------|--------|------|
| **IQ55-12a** | 从 `tool_quality.db` / agent.log 聚合 P50/P95 per tool | `data/ops/tool-latency-profile.json` |
| **IQ55-12b** | 标红 P95>30s 工具（含 `crash_tool` score 0） | closeout 表 |
| **IQ55-12c** | 根因：超时配置 / 子进程 / 网络 / 重试风暴 | phase0 一页 |
| **IQ55-12d** | （7.5）逐项修或降级/禁用 | P95<10s 复测 |

---

## 波次 3 — P1（5.5 需 P1.1；其余并行 backlog）

| ID | 任务 | 验证 |
|----|------|------|
| **IQ55-20** | intent 生产：`MIMIR_INTENT_PREDICTOR=1`（默认常开）+ 7d hits | brain_metrics `intent.total_hits` ≥1 |
| **IQ55-21** | WM 生产：依赖 **IQ55-OPS-01** | log + baseline 对比 |
| **IQ55-22** | brain_metrics：SELF-LOOP 每周 `brain_metrics_snapshot.py` | `brain-metrics-YYYY-MM-DD.json` 序列 |
| **IQ55-23** | AUTO_ANALYSIS 闭环验：`MIMIR_AUTO_ANALYSIS=1` 产物路径 | ops 目录有分析 JSON/MD |
| **IQ55-24** | MW-03 后续：`ToolDispatchContext` 接入 `agent_loop`（可选） | 设计 ≤1 粒，非 5.5 硬门槛 |

---

## 波次 4 — P2 / 长期 backlog

| ID | 任务 | 何时 |
|----|------|------|
| **IQ55-30** | 元认知三问：记忆写入 + 周计数≥10 | 6.5 |
| **IQ55-40** | 记忆 55k 上限巡检 + 到期/精简策略 | 8.5 |
| **IQ55-41** | IC 顾问真实场景复验（MW-05 后） | P2 |
| **IQ55-50** | 模型路由：简单任务 flash / 复杂 pro | 7.5 |
| **IQ55-60** | 跨会话意图 1 轮命中（WM+intent 数据后） | 8.5 |
| **IQ55-61** | VoE / surprise 与 WM 联调（已有 env） | backlog |
| **IQ55-90** | `iq55-closeout.md` + IQ rubric 重评 | 达 5.5 后 |

### 保持 BLOCK / 不做

| ID | 说明 |
|----|------|
| **IQ-12** | WM B2 RECALL — 刘哥每步问我 |
| **WM-B5** | LLM WM 预测 — deferred |
| **EV-VISION** | 刘哥 DEFER |

---

## 与旧链关系

| 链 | 状态 |
|----|------|
| §11 IQ-17 | 收官；勿重复 IQ-31～34 实现 |
| §12 ENG-WF | 全 [x] |
| §13 MW | 全 [x]；运维见 **波次 1** |
| **§14 IQ-55** | **当前主执行轨**（Mimir PRIMARY_EXECUTOR） |

## Mimir 开场（复制到 §0）

```
主线：IQ-55 达 5.5。下一粒：./scripts/mimir_iq55_run_next.sh --dry-run
真源：docs/MIMIR_IQ55_ROADMAP.md · 勘误：docs/phase0/iq55-truth-refresh.md
禁止：WM-B5 · 重复合 IQ-31～34 · 未验宣称进化 ok%
P0：搜索≤40% · ledger applied · 工具延迟画像
刘哥已开：MIMIR_WM_PREDICTOR=1（见 iq55-baseline / ops closeout）
```
