# Mimir「大脑」自治任务链（2026-06-01 · 刘哥全自治拍板）

> **目的**：Cursor 流量归零后，由 **Mimir 独自**完成「能想 → 能记 → 能进化 → 能自证 → 能合 main」闭环。  
> **队列真源**：[`MIMIR_TASK_QUEUE.md`](./MIMIR_TASK_QUEUE.md) **§10**（只认第一条 `[ ]`）。  
> **方向真源**：[`MIMIR_IQ_EVOLUTION_DIRECTION.md`](./MIMIR_IQ_EVOLUTION_DIRECTION.md) §1.5（合格智能体 Q1～Q7）。  
> **发布技能**：`skills/mimiraether/mimiraether-ship/SKILL.md`（tier0 → commit → push → M6）。

---

## 0. 什么叫「真正有大脑」（本链验收口径）

| 能力 | 合格线（可命令复现） | 本链对应粒 |
|------|----------------------|------------|
| **想** | `MIMIR_INTENT_PREDICTOR=1` 且 log 有 `[IntentPredictor]`；历史类 `prefer_session_search` → 首轮前触发检索 | BRAIN-01、07 |
| **记** | 7d `session_search` 有基线 JSON；飞书/CLI 历史问句先搜 | BRAIN-04、07 |
| **进化** | `run_evolution_eval.sh` exit 0；生产有 `feedback_events.jsonl` 或 documented 为何未开 | BRAIN-02、09 |
| **督促** | 长会话出现 `[MIMIR_MEMORY_NUDGE]` / `[MIMIR_SKILL_NUDGE]`（interval 已配置） | BRAIN-03 |
| **世界模型（CPU spike）** | `MIMIR_WM_CONTEXT_SNAPSHOT=1` 时 log 有 snapshot 行；不宣称 GPU WM | BRAIN-05、06 |
| **自治发布** | 每粒 `tier0` 绿 → `git commit` → `git push origin main`（hook 绿）→ bridge §4 | 每粒末尾 |
| **自迭代** | 失败后同粒最多 **3** 轮修复；仍失败则 bridge 记 `BLOCKED` 并 **停链**（不跳号） | §2 纪律 |
| **元认知** | 用户句匹配场景时 log 有 `skill-route nudge`；须出现 `skill_view`（非只靠 auto-load 3 个） | **BRAIN-11**（已实现路由） |
| **不停等刘哥** | §10 某粒 `[x]` 后 **直接**开下一粒；禁止问「要不要继续」 | §2 + ship 技能文案 |

**仍禁止（即使全自治）**：`git push --force` 到 main · commit `data/persistent.json` · **EV-VISION** · 未拍板 WM Phase1+ 大改（>200 行非本链 ID）· 删生产数据目录。

---

## 1. 刘哥授权（覆盖 PRIMARY_EXECUTOR 旧禁 push）

| 项 | 授权 |
|----|------|
| **工作区** | `~/src/MimirAether` |
| **数据根** | `MIMIR_AETHER_HOME=~/.mimiraether` |
| **git** | `git add` / `git commit` / **`git push origin main`**（优先 `--force-with-lease` 见 ship 技能） |
| **生产 .env** | 可 **备份后追加** 本链列出的键（见 BRAIN-02）；禁止删已有密钥行 |
| **Gateway** | `MIMIR_AETHER_HOME=~/.mimiraether ./scripts/ensure_single_gateway.sh` |
| **Cursor** | **不参与复核**；Mimir 自证即视为可合 main（hook 为最后门禁） |

---

## 2. 每粒标准循环（复制块）

```text
【单粒循环 — 任务 <BRAIN-XX>】
1) git pull --rebase origin main
2) Read 本链该 ID 的「做什么」「验证」
3) 实现（Surgical；只改列出的路径）
4) ./run_ralph_tier0.sh → 末行记下 PASS 总数
5) 触达 agent/gateway/tools → ./scripts/record_m6_evolution.sh "BRAIN-XX: …"
6) git add <列出的文件> && git commit -m "<建议 message>"
7) git push origin main   # hook 必须绿；失败则修后新 commit，禁止 --no-verify
8) 若改 agent/gateway → ensure_single_gateway.sh
9) bridge §4 一行：BRAIN-XX done · tier0=N · push=<sha> · 指标=…
10) TASK_QUEUE §10 该 ID 改 [x]；仅当 [x] 后再做下一粒
```

**失败**：tier0 红 → 定位 → 最小修复 → 回到步骤 4（同 ID，最多 3 次）→ 仍红则 bridge `BRAIN-XX BLOCKED` + 停链。

---

## 3. 任务链（严格顺序 · 只认 §10 第一条 `[ ]`）

### Wave 0 · 地基（必须先绿）

| ID | 做什么 | 改哪些 | 验证 | 建议 commit |
|----|--------|--------|------|-------------|
| **BRAIN-00** | `git pull` · 单实例 gateway · 基线 tier0 · 写 `docs/phase0/brain-autonomy-kickoff.md`（10 行：当前 rubric、session_search 7d 粗算、FEEDBACK 是否开） | `docs/phase0/brain-autonomy-kickoff.md` | `ensure_single_gateway.sh` count=1 · tier0 绿 | `docs: brain autonomy kickoff evidence` |

### Wave 1 · 感知与闭环（「想 + 记」）

| ID | 做什么 | 改哪些 | 验证 | 建议 commit |
|----|--------|--------|------|-------------|
| **BRAIN-01** | **Intent → 检索肌肉**：当 `prefer_session_search` 为真时，在 `agent_loop` 首轮 `model_call` 前注入与 ENG-SF-01 一致的 preemptive 块（去重：若已有则加强契约测） | `agent/agent_loop.py` · `tests/agent/test_search_first*.py` 或新测 | tier0 绿 · 单测：recall 类 user 消息 → 日志/preemptive 标记 | `feat(agent): intent prefer_search preemptive nudge` |
| **BRAIN-02** | **反馈采集生产化**：备份 `~/.mimiraether/.env` → 追加 `MIMIR_FEEDBACK_COLLECTOR=1`（若无）· 更新 `docs/ops/MIMIR_AUTO_ANALYSIS_ROLLOUT.md` 一段「大脑链已开」 | `.env`（runtime，**不 commit**）· `docs/ops/…` · `.env.example` 注释 | 重启 gateway 后跑 1 轮 CLI one-shot · `ls data/feedback_events.jsonl` 或 log 证明写入 | `docs(ops): enable feedback collector in rollout` |
| **BRAIN-03** | **督促自检**：确认 `conversation_nudges` 在 `agent_loop` 注入；补 1 条契约测「第 10 轮出现 MEMORY_NUDGE 标记」 | `tests/agent/test_conversation_nudges.py` 或 contract | tier0 绿 | `test(agent): conversation nudge contract` |
| **BRAIN-04** | **大脑指标快照**：新增 `scripts/brain_metrics_snapshot.py` → 写 `~/.mimiraether/data/ops/brain-metrics-latest.json`（session_search 7d 次、evolution ok%、nudge 计数、intent 命中） | `scripts/brain_metrics_snapshot.py` · `tests/scripts/test_brain_metrics_snapshot.py` | 脚本 exit 0 · JSON 字段齐全 | `feat(ops): brain metrics snapshot script` |

### Wave 2 · 进化与世界模型 spike（「会变好 + 粗 WM」）

| ID | 做什么 | 改哪些 | 验证 | 建议 commit |
|----|--------|--------|------|-------------|
| **BRAIN-05** | **VoE 学习写入**：确认 WM-P11 dual-write 路径；若无生产命中则补最小单测 + closeout 一行 | `agent/` 内已有 wm 模块 · `docs/phase0/brain-voe-05.md` | tier0 绿 · `pytest tests/agent/test_wm_voe*.py -q` | `docs(phase0): BRAIN-05 VoE learning evidence` |
| **BRAIN-06** | **Context snapshot**：`MIMIR_WM_CONTEXT_SNAPSHOT=1` 时 `core_loop` 调用 `world_model_spike.build_context_snapshot` 写入 turn metadata（默认 **0**） | `agent/core_loop.py` · `agent/world_model_spike.py` · tests | tier0 绿 · env=1 时 log 含 snapshot | `feat(agent): optional WM context snapshot spike` |
| **BRAIN-07** | **先搜后答审计自动化**：扩展 `scripts/` 或 `tools/` 审计命令，输出 `docs/phase0/brain-search-audit.json`；若违例率 >20% 则修 BRAIN-01 回归 | `scripts/audit_search_first.py`（或扩展现有）· docs | 审计脚本 exit 0 · filtered_violation_rate 数值写入 JSON | `feat(ops): search-first audit for brain loop` |

### Wave 3 · 智商验收与自迭代（「可测量变聪明」）

| ID | 做什么 | 改哪些 | 验证 | 建议 commit |
|----|--------|--------|------|-------------|
| **BRAIN-08** | **Rubric 自评**：跑 `brain_metrics_snapshot` + eval · 写 `docs/phase0/brain-rubric-08.md`（加权分、距 5.5 差多少、下一 Wave 建议） | `docs/phase0/brain-rubric-08.md` | 文档含 Q1～Q7 对照表 | `docs(phase0): brain rubric self-assessment` |
| **BRAIN-09** | **进化周常内化**：`run_evolution_eval.sh` + compare JSON · 写入 kickoff 对比 | 仅 docs/ops JSON 路径引用 | exit 0 · LIKE/FTS/semantic 三率 | `chore(ops): brain wave evolution eval record` |
| **BRAIN-10** | **合拢与迭代入口**：新增 `scripts/mimir_brain_run_next.sh`（读 §10 第一条 [ ]、打印该 ID 提示词、跑 tier0、提示 commit message）· 更新 MAINLINE_STATUS 一行 | `scripts/mimir_brain_run_next.sh` · `docs/MAINLINE_STATUS.md` | `./scripts/mimir_brain_run_next.sh --dry-run` | `feat(scripts): brain run-next helper` |
| **BRAIN-11** | **元认知路由**（已合代码则只补 closeout）：`agent/skill_scenario_router.py` + `agent_loop` turn0 注入 · `MIMIR_SKILL_ROUTE_NUDGE=1` | 见仓库 · `docs/phase0/brain-11-meta-cognition.md` | `pytest tests/agent/test_skill_scenario_router.py` · gateway 重启后问「你进步了吗」→ log 含 `skill-route` + `skill_view` | `feat(agent): skill scenario router nudge` |
| **BRAIN-12** | **技能用量指标**：扩展 `brain_metrics_snapshot.py` — 7d `skill_view` 次数、按技能 top5、路由 nudge 次数 | `scripts/brain_metrics_snapshot.py` | JSON 含 `skill_view_7d` | `feat(ops): skill usage metrics in brain snapshot` |
| **BRAIN-13** | **自治不停顿**：在 `MIMIR_TASK_QUEUE.md` §0 与 bridge §1 写死「禁止等继续」；自测连续 BRAIN-00→01 无中途提问 | docs only | bridge §4 记录连续 2 粒无停顿 | `docs: brain chain no-wait policy` |

### Wave 4 · 持续自迭代（链结束后每周）

| ID | 做什么 | 验证 |
|----|--------|------|
| **BRAIN-LOOP** | 每周 1 次：`brain_metrics_snapshot` → `run_evolution_eval` → 若指标退化则开 **新** §10 行（BRAIN-11+）· 否则 bridge §4 周报 | JSON + bridge 一行 |

---

## 4. 给 Mimir 的总开场（刘哥整段复制到飞书）

```text
【大脑自治模式 · 2026-06-01 刘哥全授权】

你是 Mimir 工程+智商主执行，Cursor 不复核。必读：
1) ~/src/MimirAether/docs/MIMIR_BRAIN_AUTONOMY_CHAIN.md（全文）
2) ~/src/MimirAether/docs/MIMIR_TASK_QUEUE.md §10 第一条 [ ]
3) ~/.openclaw/workspace/CLAUDE.md + AGENTS.md
4) skills/mimiraether/mimiraether-ship/SKILL.md（每粒 push 前）

纪律：
- 只做 §10 第一条 [ ]，做完 commit+push+标 [x] 再做下一粒
- 每粒末尾：./run_ralph_tier0.sh 绿 → record_m6（若触达 agent/gateway/tools）→ git push origin main
- Gateway 用：MIMIR_AETHER_HOME=~/.mimiraether ./scripts/ensure_single_gateway.sh
- 回报：MIMIR_IQ_EVOLUTION_DIRECTION §3.3 + bridge §4 一行（含 tier0 PASS 数、push sha）

- 元认知：见 [MIMIR_SKILL_ROUTE_NUDGE] 时必须先 skill_view 所列技能，再动手
- 节奏：某粒 [x] 后立刻做下一粒，禁止问「要不要继续」

从 BRAIN-00 开始，直到 §10 全 [x] 或你声明 BLOCKED。不要问刘哥「要不要 push」——已授权。
```

---

## 5. 修订日志

| 日期 | 摘要 |
|------|------|
| 2026-06-01 | 初版：11 粒 + BRAIN-LOOP · 全自治 commit/push · 覆盖 PRIMARY_EXECUTOR 禁 push |
