# Mimir 自我完善任务链（真源 · 2026-06-01）

> **队列**：[`MIMIR_TASK_QUEUE.md`](./MIMIR_TASK_QUEUE.md) **§10** — 只认第一条 `[ ]`  
> **自评锚点**：执行器 **8/10** · 元认知 **2/10** → 收官目标 **≥5/10**（M1～M6 可测）

---

## 0. 自评缺口 → 任务

| 缺口 | 任务 |
|------|------|
| 73/78 未 skill_view | SELF-02 路由 · SELF-03/04 指标 |
| 等「继续」12 次 | SELF-06 · SELF-07 |
| 评估不先 self-audit | SELF-02 + 路由（`9ccc1b9`） |
| 无 brainstorming 门控 | SELF-02 多步→brainstorm+planner |
| 未查 /health、ok% | SELF-04 · SELF-05 |
| 告警 98% 假阳性 | SELF-08 |
| 冲动未固化 | SELF-09 memory |
| AUTO_EVOLVE 空 | SELF-10 |
| 工程智商债 | SELF-11～16 |
| 收官 | SELF-17 |

---

## 1. 收官合格线（M1～M6）

| ID | 合格 |
|----|------|
| M1 | 7d `skill_view` ≥10 次且 ≥3 种技能 |
| M2 | 路由后 5 条抽样 ≥4/5 首轮含 skill_view |
| M3 | bridge 连续 3 粒无「要不要继续」 |
| M4 | `brain-metrics-latest.json` 齐全 |
| M5 | 末粒 tier0 绿 |
| M6 | `self-improvement-closeout.md` 2→?/10 |

---

## 2. 单粒循环

git pull → 读本 ID → 实现 → tier0 → record_m6（若改 agent/gateway/tools）→ commit → push → gateway（若改 agent）→ bridge 一行 → §10 [x] → **立刻下一粒**。

---

## 3. 任务表

| ID | 摘要 |
|----|------|
| **SELF-00** | baseline.md + health check（非飞书内 restart）+ tier0 |
| **SELF-01** | 路由 3 场景冒烟 + smoke.md |
| **SELF-02** | 扩展 skill_scenario_router |
| **SELF-03** | audit_skill_usage.py |
| **SELF-04** | brain_metrics_snapshot.py |
| **SELF-05** | 更新 self-audit 技能 |
| **SELF-06** | 禁止等继续（文档） |
| **SELF-07** | mimir_self_run_next.sh |
| **SELF-08** | monitor 真/假阳性 closeout |
| **SELF-09** | memory 固化元认知（勿 commit persistent） |
| **SELF-10** | FEEDBACK + AUTO_EVOLVE 文档/.env |
| **SELF-11** | preemptive session_search |
| **SELF-12** | nudge 契约测 |
| **SELF-13** | search-first 审计 |
| **SELF-14** | VoE + WM snapshot |
| **SELF-15** | evolution eval |
| **SELF-16** | rubric 自评 |
| **SELF-17** | closeout M1～M6 |
| **SELF-LOOP** | 每周 metrics+audit+eval |

---

## 4. 提示词（节选）

### SELF-00

```text
SELF-00：Read 本文件 §2。pull · `curl -sf localhost:18999/health`（勿在飞书 turn 内 restart gateway）· tier0。
写 docs/phase0/self-improvement-baseline.md（元认知2/10、执行器8/10、78技能、等继续12次）。
commit push · [x] · 禁止问继续。
```

### SELF-01

```text
SELF-01：gateway 重启后 3 句：①你进步了吗 ②tier0失败根因 ③执行SELF-02下一粒。
log 含 skill-route + skill_view → self-01-router-smoke.md · commit push · [x]
```

### SELF-17

```text
SELF-17：brain_metrics_snapshot + audit_skill_usage → self-improvement-closeout.md 填 M1～M6。
commit push · [x]
```

---

## 5. 给 Mimir 开场（刘哥复制）

```text
【自我完善 · 全自治】
Read ~/src/MimirAether/docs/MIMIR_SELF_IMPROVEMENT_CHAIN.md
TASK_QUEUE §10 第一条 [ ] 起，做到 SELF-17。
./scripts/mimir_self_run_next.sh --dry-run 看当前粒。

铁律：
· [MIMIR_SKILL_ROUTE_NUDGE] → 先 skill_view 再动手
· 评估/进步 → 先 self-audit + brain_metrics_snapshot
· 每粒 [x] 后立刻下一粒，禁止问「要不要继续」
· tier0 绿 → push origin main
· Gateway：**飞书会话内禁止**跑 `ensure_single_gateway.sh`（会杀掉当前 gateway、任务中断）。
  仅在本机 shell、无进行中飞书对话时：`MIMIR_AETHER_HOME=~/.mimiraether ./scripts/ensure_single_gateway.sh`
  或改 agent 后由刘哥/Cursor 在 shell 重启。

从 SELF-00 开始。
```
