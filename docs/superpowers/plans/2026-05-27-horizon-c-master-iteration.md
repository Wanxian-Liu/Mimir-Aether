# Horizon C 主迭代计划（Backlog §19）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 backlog **§19** 单一入口下，按波次清空 Hermes/OpenSpace 学习债、§8 工程余债与运维验收，并保持 tier0 + M6 绿。

**Architecture:** §18.2 保留颗粒 ID 与论证链接；§19.1 定义执行顺序；本文件定义每波的 bite-sized 步骤、文件触点与验证命令。拍板项（ADR-002、世界模型、rubric 5.5）用 **Gate** 隔离，不混入工程 Wave。

**Tech Stack:** Python 3.12 · `agent/` · `tools/` · `./run_ralph_tier0.sh` · `MIMIR_AETHER_HOME=~/.mimiraether`

**真源：** `docs/MIMIR_EXEC_BACKLOG.md` §19 · `docs/hermes-comparison-detailed.md` · `docs/DEVELOPMENT_NORTH_STAR.md`

---

## 执行约定（每粒必做）

1. `git pull`（若在 feature 分支则 rebase `main`）
2. 实现 → 单测/契约测 → `./run_ralph_tier0.sh`
3. `./scripts/record_m6_evolution.sh "…; tier0 N+2"`
4. backlog §18.2 + §19.1 标 `[x]` · bridge §4 一行
5. 触达 `agent|gateway`：**Gateway 硬重启** + `/health`（记入 closeout）

**禁止：** 未授权 `MIMIR_AUTO_EVOLVE=1` 生产切换 · 未拍板 WM 大 diff · 提交 `data/persistent.json`

---

## Phase 0 — 部署收口（W0 · 0.5 天）

**Backlog：** `OPS-DEPLOY-W9` · `OPS-IQ-SMOKE-49`

| 步骤 | 动作 | 验证 |
|------|------|------|
| 0.1 | 确认 `main` 含 `71940ce`+（Wave 9 + 粒 B） | `git log -1 --oneline` |
| 0.2 | 部署到 `$MIMIR_AETHER_HOME` · Gateway 硬重启 | `curl -s http://127.0.0.1:18999/health` |
| 0.3 | Mimir：`/new` + 问「上次 key_decisions」 | cross-session 块可见 |
| 0.4 | bridge §4 · backlog OPS-* `[x]` | — |

---

## Wave 10 — Curator + 可观测补强（W1–W2 · ~1.5 周）

**Goal:** 技能闲置治理可运行；tool cache 与 SDH 可测。

**Backlog IDs:** `HERM-CUR-02` · `HERM-TGR-02` · `HERM-SDH-02`

### Task 1: HERM-CUR-02 — skill_curator 生命周期闭环

**Files:**
- Modify: `agent/skill_curator.py`
- Modify: `agent/core_loop.py`（或 `post_close` / cron 钩子，按现有 curator 调用点）
- Create: `tests/agent/test_skill_curator_lifecycle.py`
- Create: `tests/contract/test_horizon_herm_cur_02.py`
- Create: `docs/phase0/herm-cur-02-closeout.md`

**现状：** `skill_curator.py` 已有 fresh/stale/dormant 阈值（30/60 天）；缺 **自动周期扫描**、**合并建议输出**、**archived 目录约定** 的 tier0 契约。

- [x] **Step 1:** 写失败测 — `scan_all_skills()` 返回 stale 列表（mock SKILL 目录 + persistent 条目）
- [x] **Step 2:** `pytest tests/agent/test_skill_curator_lifecycle.py -v` → FAIL → PASS
- [x] **Step 3:** 实现 `run_lifecycle_pass()` + `build_lifecycle_report`
- [x] **Step 4:** `MIMIR_SKILL_CURATOR_ON_CLOSE` + `schedule_skill_curator_lifecycle_pass` in close pipeline
- [x] **Step 5:** contract 测 + tier0 **497+2** PASS
- [ ] **Step 6:** commit `feat(agent): HERM-CUR-02 skill curator lifecycle pass`（工作区待 commit）

### Task 2: HERM-TGR-02 — tool cache 观测

**Files:**
- Modify: `agent/tool_call_cache.py`
- Modify: `agent/exec_mixin.py`（可选 debug log）
- Create: `tests/agent/test_tool_call_cache_metrics.py`

- [x] **Step 1:** 测 `get_stats()` → `{hits, misses, size}`

- [x] **Step 2:** 实现计数器；`MIMIR_TOOL_CACHE_LOG=1` 时 info 级单行

- [ ] **Step 3:** commit `feat(agent): HERM-TGR-02 tool cache metrics`（工作区待 commit）

### Task 3: HERM-SDH-02 — hints 进 system prompt

**Files:**
- Modify: `agent/prompt_builder.py`
- Modify: `agent/subdirectory_hints.py`
- Create: `tests/agent/test_subdirectory_hints_prompt.py`

- [x] **Step 1:** 测 `build_system_prompt_parts()` 在 cwd 含 `AGENTS.md` 时含 hint 段

- [x] **Step 2:** `SubdirectoryHintTracker.prompt_block()` + env `MIMIR_SUBDIR_HINTS_IN_SYSTEM`（默认关）

- [ ] **Step 3:** commit `feat(agent): HERM-SDH-02` · closeout `herm-sdh-02-closeout.md`（工作区待 commit）

**Wave 10 出口：** §19.1 前三行 `[x]` · tier0 计数递增 · evolution_log 3 行

---

## Wave 11 — 质量与检索核心（W3–W4 · ~2 周）

**Goal:** 工具质量进入默认路径；session_search 排序对标 OpenSpace。

**Backlog IDs:** `OS-TQM-02` · `OS-SCH-02`

### Task 4: OS-TQM-02 — ToolQualityManager 接线

**Files:**
- Modify: `agent/prompt_builder.py`
- Modify: `agent/core_loop.py` 或 `tools/registry.py`
- Modify: `agent/tool_quality.py`
- Create: `tests/contract/test_horizon_os_tqm_02.py`

- [ ] **Step 1:** 读 `tool_quality.py` 现有 API；列 3 个调用点（tool 选择前 / 结果后 / prompt 摘要）

- [ ] **Step 2:** 失败契约测：`MIMIR_TOOL_QUALITY=1` 时 prompt 含 degraded tools 警告

- [ ] **Step 3:** 最小接线 + tier0

- [ ] **Step 4:** closeout `os-tqm-02-closeout.md`

### Task 5: OS-SCH-02 — BM25 + 语义融合排序

**Files:**
- Modify: `tools/session_search_tool.py`
- Modify: `mimicore` 或本地 `sessions_search` 层（按现有 hybrid 实现）
- Create: `tests/tools/test_session_search_fusion_rank.py`
- Extend: `scripts/run_memory_retrieval_benchmark.py`（可选一列 `fusion_hit_rate`）

- [ ] **Step 1:** 读 OpenSpace 对标笔记（`hermes-comparison-detailed.md` §search）

- [ ] **Step 2:** 实现 `rank_fusion(lexical, semantic)` — 先 RRF 或加权，文档化取舍

- [ ] **Step 3:** 基准对比：hybrid vs fusion — 记录 JSON，不要求全面超越 LIKE

- [ ] **Step 4:** tier0 + commit

**Wave 11 出口：** OS-REV-01 / OS-TOOL-SRCH-01 **解锁**

---

## Wave 12 — P1 抛光（W5–W6 · ~1.5 周）

| Task | ID | 要点 |
|------|-----|------|
| 6 | HERM-SCR-01 | think 块状态机 · `core_loop` 流式路径 |
| 7 | HERM-RED-02 | `data/redact_rules.json` 或等价 · 运维文档 |
| 8 | HERM-CTX-02 | 飞书 1 条自然语言引用 · Mimir 冒烟 |
| 9 | OS-REV-01 | 依赖 TQM-02 · skill 描述评分 hook |

**每 Task 模板：** 失败测 → 实现 → contract → tier0 → closeout → commit（与 Wave 10 相同）

---

## Wave 13 — 工具搜索（W6 · ~1 周）

### Task 10: OS-TOOL-SRCH-01

**Files:** 新模块 `agent/tool_ranker.py` 或 `tools/tool_search.py` · 注册到 registry · 单测

- [x] 从 `skills_list` + tool schema 建索引
- [x] `session_search` 模式复用（不复制 OpenSpace 代码）
- [x] tier0 契约：≥3 断言

---

## Wave 14 — 跨会话战略调研（W7–W8 · ~2 周）

### Task 11: P3-XSR-01

**Deliverable（仅文档 + 可选 spike，无生产默认切换）：**

- [ ] `docs/proposals/p3-cross-session-retrieval.md`：三层注入（核心全量 / Top-N / RAG）
- [ ] 对照 Hermes 注入策略（`hermes-comparison-detailed.md`）
- [ ] 与 **ADR-002** 关系一节 → 提交刘哥 **Gate ADR-002**
- [ ] backlog `[x]` · **不** 改 `SESSION_SEARCH_BACKEND` 生产默认

---

## Gate 拍板（与工程轨并行 · 刘哥）

| Gate | 文档 | 工程解锁 |
|------|------|----------|
| **G-ADR-002** | `docs/phase0/adr-002-write-spike.md` | ENGINE-P3W-01 · 注入路径 |
| **G-WM** | `world-model-evolution-plan.md` Phase 0 | 新 plan `wm-phase0-*.md` |
| **G-RUBRIC-55** | `MIMIR_IQ_EVOLUTION_DIRECTION.md` | IQ-EVO 续 Wave（行为清单） |
| **G-VISION** | bridge EV-VISION-DEFER | 识图路径 |

**规则：** Gate 未 `[approved]` 前，Cursor **不得** 开对应实现 Wave。

---

## Wave 15+ — 工程 icebox（W9+ · 按需）

| ID | 说明 |
|----|------|
| ENGINE-WS-01 | WebSocket 推理心跳 — `gateway/` |
| ENGINE-ROLLBACK-01 | 进化回滚 — `agent/evolution_audit.py` 邻域 |
| ENGINE-GW-01 | `GATEWAY_STABILITY_BACKLOG.md` 逐项 |
| GH-ICE-21-22 | GitHub 评论刷新 / 关或 wontfix |

---

## IQ rubric 5.5 战役（G-RUBRIC-55 批准后 · W9–W12）

**Goal:** 行为证据，非刷分。

| 维度 | 当前 exception | 目标证据 |
|------|----------------|----------|
| #1 学习能力 | ~2.0 | 连续 7d evolution ok=1 样本 |
| #3 反馈 | 已升 | 飞书 follow-up 闭环 3 例 |
| #8 意图 | 4.0 | IntentPredictor 生产 7d 无回归 |

- [ ] Mimir 填 `docs/phase0/iq-rubric-55-evidence.md` 每周一行
- [ ] Cursor 只实现 **已挂 backlog ID** 的 engineering 粒
- [ ] 达标后更新 `MIMIR_IQ_EVOLUTION_DIRECTION.md` §1.1

---

## 进度看板（人工更新）

| Wave | 状态 | tier0 | 备注 |
|------|------|-------|------|
| 0 部署 | [ ] | 488+2 | |
| 10 | [ ] | | CUR/TGR/SDH |
| 11 | [ ] | | TQM/SCH |
| 12 | [ ] | | P1 抛光 |
| 13 | [x] | | ToolRanker |
| 14 | [ ] | | P3 调研 |
| 15+ | [ ] | | icebox |

---

## Self-Review（plan author）

- [x] §19.1 每个 `[ ]` ID 在本计划有 Wave 或 Gate
- [x] Wave 10 Task 1 含具体文件与测试骨架（非 TBD）
- [x] 拍板项未混入 Wave 10–13 实现
- [x] P3-XSR 与 ADR-002 顺序正确（先调研再拍板）

---

## Execution Handoff

**Plan complete and saved to** `docs/superpowers/plans/2026-05-27-horizon-c-master-iteration.md`.

**Two execution options:**

1. **Subagent-Driven (recommended)** — 每 Task 派生子 agent，Task 间你做 review
2. **Inline Execution** — 本会话按 Wave 10 Task 1 逐步执行，每 Task 末 checkpoint

**建议下一动作：** Phase 0 部署（OPS-DEPLOY-W9）→ Wave 10 Task 1（HERM-CUR-02）。

Which approach?
