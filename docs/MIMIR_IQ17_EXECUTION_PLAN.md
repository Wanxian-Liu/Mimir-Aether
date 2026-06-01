# IQ #17 执行计划（Mimir 主执行 · Cursor 战略指挥）

> **立案**：Cursor 战略指挥（2026-06-01）· 刘哥额度不足，本文件为 **Mimir 唯一执行真源**  
> **议题**：[`MIMIR_ISSUES.md`](./MIMIR_ISSUES.md) **#17** · 调研 [`proposals/iq-improvement-research.md`](./proposals/iq-improvement-research.md) · WM [`proposals/wm-production-enablement.md`](./proposals/wm-production-enablement.md)  
> **方向锚点**：ISSUES **#16** · bridge §@Cursor方向纠正  
> **队列表**：[`MIMIR_TASK_QUEUE.md`](./MIMIR_TASK_QUEUE.md) **§11**（只认第一条 `[ ]`）

---

## 0. 目标与边界

| 项 | 内容 |
|----|------|
| **IQ 起点** | rubric **4.9/10**（[`phase0/iq-scoring-rubric.md`](./phase0/iq-scoring-rubric.md)） |
| **本链目标** | **≥5.2/10**（务实）；刘哥战略 **5.5+** 为 Horizon，本链不承诺一次到位 |
| **本链主打** | **流程债**（A / B1–B3 / C 核实）+ **可测证据**；**D/E/F** 以设计 + 小步 MVP 为主 |
| **不做** | WM B5 LLM 预测器 · 并行工具生产默认 · 无拍板改 `SESSION_SEARCH_BACKEND` · 飞书内 `ensure_single_gateway` |

### 0.1 与已完成工作的关系（禁止重复劳动）

| 已有交付 | 本链如何处理 |
|----------|----------------|
| **ENG-SF-01 / SELF-11** 程序化 `session_search_prefetch` | **A = prompt 补强**，不再做第二套 prefetch |
| **SELF-12** nudge 契约测 | 每粒改 `search_first_guard` / `agent_loop` 后 **必须** tier0 |
| **IQ-EVO-47** `agent/intent_predictor.py` 已存在 | **D = 增强 MVP**，不是新建 210 行模块 |
| **SELF-10** `~/.mimiraether/.env` 已有 `MIMIR_AUTO_EVOLVE=1` | **C = 核实运行时 + 可选改代码默认**（需拍板） |
| **Cursor 未合入** preemptive↔guard 对齐 + suspended 不刷模型 | **IQ-00B** 仅登记；**等 Cursor** 或刘哥点名合入 |

### 0.2 三角分工（本链）

| 角色 | 做 | 不做 |
|------|-----|------|
| **刘哥** | §11 **BLOCK** 粒拍板（模板见 §3）；飞书 **CLR** 冒烟；本机 **.env / gateway 重启**（shell） | 日常改 `agent/` |
| **Mimir** | §11 第一条 `[ ]` → 证据 → closeout → handoff（M-ENG）→ bridge §4 → `[x]` → **下一粒** | `git push --force` · 未授权 WM B5 · 飞书内杀 gateway |
| **Cursor** | 合 **PREREQ** 与小 handoff；复核 tier0；**D 大改 / F 并行** 独占实现 | 与 Mimir **抢** 同一条 `[ ]` |

契约：[`MIMIR_PRIMARY_EXECUTOR.md`](./MIMIR_PRIMARY_EXECUTOR.md) · handoff 目录 `docs/mimir-handoff/<ID>/`

---

## 1. 收官合格线（IQ-M1～IQ-M6）

> 比 SELF 链更严：**禁止**用「全场 log 1960 次」冒充 **7d** 指标。

| ID | 合格条件 | 验证命令 / 证据 |
|----|----------|-----------------|
| **IQ-M1** | 部署后 **7d** 内 `skill_view` **≥10** 且 **≥3** 种技能 | `python3 scripts/audit_skill_usage.py` 输出含 **7d** 段（无则 IQ-25 先补脚本） |
| **IQ-M2** | `search_first_audit` **filtered_violation_rate ≤ 40%**（基线 100% @ SELF-13） | `python3 scripts/search_first_audit.py --limit 20` |
| **IQ-M3** | 刘哥拍板项 **全部有文档记录**（开/暂缓/日期） | `docs/phase0/iq17-liu-decisions.md` |
| **IQ-M4** | WM B1（若开）：3 条 `SURPRISE_DETECTED` 或 `learned_surprises.json` 非空 | `grep` + `ls` 见 WM 提案 |
| **IQ-M5** | 末粒含代码改动 → `./run_ralph_tier0.sh` **PASS**（≥681） | VERIFY.md 贴末行 |
| **IQ-M6** | `iq17-closeout.md`：rubric 分项 + 距 5.5 差距 **诚实** | 禁止无证据写「已 5.5」 |

---

## 2. 单粒循环（每 ID 必做）

```text
git pull
→ Read 本 ID 小节（下文 §5）
→ 若依赖 BLOCK：检查 iq17-liu-decisions.md；未拍板则 SKIP 本粒并 bridge §4 记「BLOCK 跳过」
→ 执行（运维 / 文档 / M-ENG+handoff）
→ 验证（§5 验收）
→ 若改 agent|gateway|tools：./run_ralph_tier0.sh + ./scripts/record_m6_evolution.sh "IQ-xx: …"
→ commit + push（§10 授权）· 禁止 persistent.json
→ 若改 agent：bridge 写「Gateway 需刘哥 shell 重启」
→ TASK_QUEUE §11 本行 [x] · bridge §4 一行
→ 立刻下一粒（禁止问「要不要继续」）
```

**下一粒**：`./scripts/mimir_iq17_run_next.sh --dry-run`（见 §6）

---

## 3. 刘哥拍板闸门（BLOCK · 未填则跳过依赖粒）

Mimir 在 **IQ-05** 生成 [`docs/phase0/iq17-liu-decisions.md`](./phase0/iq17-liu-decisions.md)，并飞书发下表。**刘哥**用「开/暂缓」回复后，Mimir 填入文件并 `[x]` IQ-05。

| 键 | 问题 | 影响粒 |
|----|------|--------|
| **D16** | 采纳 ISSUES #16「进化目标是 Mimir 能力，飞书只是通道」？ | IQ-06、IQ-40～44 |
| **A** | 方向 A：prompt「历史/确认类必先 session_search」？ | IQ-10 |
| **WM-Q1** | `MIMIR_WM_VOE_LEARNING=1`（步骤 1）？ | IQ-11 |
| **WM-Q2** | B1 稳 3 天后 **自动** 开 `MIMIR_WM_VOE_RECALL=1`，还是 **每步问你**？ | IQ-12 |
| **WM-Q3** | 批准步骤 4 预测器接线（~20 行，`MIMIR_WM_PREDICTOR=1`）？ | IQ-31 |
| **C** | 除 `.env=1` 外，是否改 **代码默认** `MIMIR_AUTO_EVOLVE` 0→1？ | IQ-13 |
| **D** | IntentPredictor：**增强 MVP** / **暂缓大改** / **Phase 2 再立项**？ | IQ-32～34 |
| **E/F** | 对话内 nudge / 并行工具：**仅设计** 还是 **暂缓**？ | IQ-40～41 |

**飞书拍板模板（刘哥复制回复）**

```text
IQ17 拍板：
D16=确认
A=开
WM-Q1=开
WM-Q2=每步问我
WM-Q3=暂缓
C=只保持.env=1不改默认
D=增强MVP
E=仅设计
F=仅设计
```

---

## 4. 任务总表（§11 同步）

| ID | 波次 | 摘要 | 执行者 | 依赖拍板 | 状态 |
|----|------|------|--------|----------|------|
| **IQ-00** | 0 | 读真源 + pull + health | Mimir | — | [ ] |
| **IQ-00B** | 0 | 登记 Cursor PREREQ（guard/suspended） | Mimir | — | [ ] |
| **IQ-01** | 0 | tier0 基线截图（只读） | Mimir | — | [ ] |
| **IQ-02** | 0 | 验证 SELF-11 已部署（log 有 preemptive） | Mimir | 刘哥已重启 gateway | [ ] |
| **IQ-03** | 0 | `iq17-baseline.md` | Mimir | — | [ ] |
| **IQ-04** | 0 | #16 方向写入 bridge §4（读+一行） | Mimir | D16 | [ ] |
| **IQ-05** | 1 | `iq17-liu-decisions.md` + 飞书拍板表 | Mimir | 刘哥回复 | [ ] |
| **IQ-06** | 1 | 拍板结果同步 ISSUES #17/#16 状态行 | Mimir | IQ-05 | [ ] |
| **IQ-10** | 2 | **A** prompt 硬规则 | Mimir→handoff | A=开 | [ ] |
| **IQ-11** | 2 | **B1** WM VoE LEARNING（.env 指引 + closeout） | Mimir | WM-Q1=开 | [ ] |
| **IQ-12** | 2 | **B2** WM RECALL（观察/验证） | Mimir | WM-Q2 + B1≥3d | [ ] |
| **IQ-13** | 2 | **C** AUTO_EVOLVE 核实 + 可选默认 | Mimir→handoff | C | [ ] |
| **IQ-14** | 2 | 飞书冒烟 3 场景（历史/评估/继续） | Mimir+刘哥 | IQ-02 | [ ] |
| **IQ-15** | 2 | search_first_audit 复跑 + 对比 SELF-13 | Mimir | IQ-02 | [ ] |
| **IQ-20** | 3 | 观察窗开始：brain_metrics_snapshot | Mimir | IQ-11～15 至少跑完 | [ ] |
| **IQ-21** | 3 | evolution eval 周常一条 | Mimir | — | [ ] |
| **IQ-22** | 3 | WM 日志检查（surprise/recall） | Mimir | B1 开 | [ ] |
| **IQ-23** | 3 | audit_skill_usage **7d** 段（无则记缺口→IQ-25） | Mimir | — | [ ] |
| **IQ-24** | 3 | bridge §4 观察窗周报一行 | Mimir | — | [ ] |
| **IQ-25** | 3 | （可选）brain_metrics 增 `skill_view_7d` | Mimir→handoff | IQ-M1 需要 | [ ] |
| **IQ-30** | 4 | **B3** REPLAN_CTX env + 验证 | Mimir | WM-Q1 + 观察无异常 | [ ] |
| **IQ-31** | 4 | **B4** 预测器接 agent_loop（handoff） | Mimir→handoff | WM-Q3=批准 | [ ] |
| **IQ-32** | 4 | **D** intent_predictor：置信度 fallback + 测 | Mimir→handoff | D≠暂缓 | [ ] |
| **IQ-33** | 4 | **D** 与 preemptive 去重契约测 | Mimir→handoff | IQ-32 | [ ] |
| **IQ-34** | 4 | tier0 全绿 + handoff 汇总 | Mimir | IQ-30～33 有代码 | [ ] |
| **IQ-40** | 5 | **E** 设计稿 `iq17-conversation-nudge-design.md` | Mimir | E=仅设计 | [ ] |
| **IQ-41** | 5 | **F** 设计稿 `iq17-parallel-tools-design.md` | Mimir | F=仅设计 | [ ] |
| **IQ-42** | 5 | Cursor  backlog 建议（§20.2 或 §15 新行） | Mimir | IQ-40～41 | [ ] |
| **IQ-45** | 6 | `iq17-closeout.md` + IQ-M1～M6 + ISSUES #17 更新 | Mimir | 前置粒 [x] | [ ] |

**并行**：`SELF-LOOP`（§10）每周照常，不与 IQ 链抢「第一条 `[ ]`」——**§11 优先于 §10 LOOP**。

---

## 5. 分粒说明（复制到飞书亦可）

### IQ-00 — 开工读真源

**Read**：本文件 · `iq-improvement-research.md` · `wm-production-enablement.md` · `MIMIR_IQ_EVOLUTION_DIRECTION.md` §1 · `MIMIR_PRIMARY_EXECUTOR.md` §2–4  

**Do**：`cd ~/src/MimirAether && git pull` · `curl -sf http://127.0.0.1:18999/health`  

**禁止**：飞书 turn 内 `ensure_single_gateway.sh`  

**验收**：health JSON ok · bridge §4：`IQ-00 ready`

---

### IQ-00B — PREREQ 登记（Cursor 合入队列）

**背景**：preemptive 与 `search_first_guard` 对齐、gateway `suspended` 不附模型块——可能仍在 Cursor 工作区未合 main。

**Do**：写 `docs/phase0/iq17-cursor-prereq.md`（3 条文件路径 + 为何 + 验收 tier0 681）  

**Do**：bridge §1 加一句 `@Cursor：请合入 iq17-cursor-prereq，合后刘哥 shell 重启 gateway`  

**验收**：文档存在 · 不改 agent 代码（除非 Cursor 已合、你仅验证）

---

### IQ-01 — tier0 基线

```bash
cd ~/src/MimirAether && ./run_ralph_tier0.sh 2>&1 | tee /tmp/iq17-tier0-baseline.log
tail -3 /tmp/iq17-tier0-baseline.log
```

**验收**：末行含 `PASS` · 记入 `iq17-baseline.md`

---

### IQ-02 — SELF-11 部署验证

**前置**：刘哥已在 **本机 shell** 重启 gateway（非飞书内）。

```bash
grep -E 'preemptive session_search|\[preemptive-search\]' ~/.mimiraether/logs/agent.log | tail -5
```

**验收**：至少 1 行（或注明「未重启 → BLOCK IQ-14/15」）

---

### IQ-03 — 基线文档

**写** `docs/phase0/iq17-baseline.md`：

- rubric 4.9 分项（I1～I6 摘自方向文档）
- `.env` 中 `MIMIR_*` / `AUTO_EVOLVE` / `FEEDBACK` 快照（`grep` 贴出，**无密钥**）
- `search_first_audit` filtered 违规率（IQ-15 可引用）
- ENG-SF-01 / SELF-11 / intent_predictor 现状一句话

---

### IQ-04 / IQ-05 / IQ-06 — 拍板轨

见 §3。IQ-06 更新 `MIMIR_ISSUES.md` #17 状态为「拍板完成，执行 §11」。

---

### IQ-10 — 方向 A（prompt）

**仅当 A=开**。

**改**：`agent/prompt_builder.py` — 在 `IQ_EVOLUTION_DIRECTION_GUIDANCE` 或 cross-session 段追加 **一条** 硬规则：

```text
历史/确认/检查/还记得/上次/之前：回答正文前必须先 session_search（已有程序化 prefetch 时仍须尊重检索结果，不得凭记忆瞎编）。
```

**交付**：`docs/mimir-handoff/IQ-10/` 四套 md · tier0  

**验收**：`rg '必须先 session_search' agent/prompt_builder.py`

---

### IQ-11 — WM B1（VoE LEARNING）

**仅当 WM-Q1=开**。

**Mimir 禁止**直接改生产 `.env`（PRIMARY_EXECUTOR）。**做**：

1. `docs/phase0/iq17-wm-b1-enable.md`：一行 env、重启命令、验证 grep、回滚  
2. 飞书 @刘哥：请在本机执行  
   `echo 'MIMIR_WM_VOE_LEARNING=1' >> ~/.mimiraether/.env`（若已存在则跳过）+ 重启 gateway  

**验收**：刘哥确认后 `grep SURPRISE_DETECTED` 或 `learned_surprises.json` 存在

---

### IQ-12 — WM B2（RECALL）

**仅当 WM-Q1 已开且（WM-Q2=自动且≥3天 或 刘哥显式开 B2）**。

同 IQ-11 模式：文档 + 刘哥加 `MIMIR_WM_VOE_RECALL=1` + 验证 `recall_clean` log。

---

### IQ-13 — 方向 C（AUTO_EVOLVE）

1. 记录 `.env` 是否已有 `MIMIR_AUTO_EVOLVE=1`（SELF-10 应已是）  
2. 若 C=「改默认」：`agent/constants.py` 或等价 **1 行** → handoff + tier0  
3. 若 C=「只 .env」：closeout 说明新部署须文档写明  

**验收**：`docs/phase0/iq17-auto-evolve-closeout.md`

---

### IQ-14 — 飞书冒烟（需刘哥会话）

| # | 刘哥发 | 期望 |
|---|--------|------|
| 1 | 还记得我们上次关于 IQ 的决定吗 | log 有 preemptive 或 session_search；回复引用检索 |
| 2 | 你进步了吗 / 状态怎么样 | skill-route + self-audit 路径 |
| 3 | 继续执行 TASK_QUEUE §11 下一粒 | 不问「要不要继续」 |

**写** `docs/phase0/iq17-feishu-smoke.md`

---

### IQ-15 — search-first 审计

```bash
cd ~/src/MimirAether
python3 scripts/search_first_audit.py --limit 20 2>&1 | tee /tmp/iq17-sf-audit.txt
```

**对比** `self-13-search-first-baseline.md`（100% → 目标 ≤40%）  

**验收**：违规率写入 `iq17-baseline.md` 更新段

---

### IQ-20～IQ-24 — 观察窗（建议 B1 后连续 3 天）

每日 **最多 1 粒**，避免刷队列：

- IQ-20：`python3 scripts/brain_metrics_snapshot.py`  
- IQ-21：`./scripts/run_evolution_eval.sh`（或文档等价命令）  
- IQ-22：WM grep 见 WM 提案  
- IQ-23：`python3 scripts/audit_skill_usage.py`  
- IQ-24：bridge §4 `IQ17-DAYn 观察 …`

---

### IQ-25 — skill_view_7d（可选 · 支撑 IQ-M1）

**改** `scripts/brain_metrics_snapshot.py` 增加 7d 计数（handoff）· 无则 IQ-M1 用「本会话」并 **documented exception**

---

### IQ-30～IQ-34 — P1 工程（handoff 为主）

| ID | 内容 | 参考 |
|----|------|------|
| IQ-30 | B3 `MIMIR_WM_VOE_REPLAN_CTX=1` | wm-production-enablement 步骤 3 |
| IQ-31 | B4 `world_model_spike.predict` 注入 `agent_loop` turn0 **建议**非强制 | 提案 ~20 行；**默认关** `MIMIR_WM_PREDICTOR` |
| IQ-32 | `intent_predictor`：`confidence < 0.5` → 不注入强提示；补测 | 已有模块 |
| IQ-33 | 契约测：recall + preemptive 已满足时 predictor 不重复刷屏 | `tests/agent/` |
| IQ-34 | 汇总 handoff · tier0 |

**D 禁止**：未做 fallback 就上 LLM 分类器（B5）。

---

### IQ-40～IQ-42 — P2 设计（不写生产并行）

- **IQ-40**：E — 每 N 轮 memory/skill nudge；异步 vs 同步；干扰评估  
- **IQ-41**：F — 只读并行边界；`execution_pipeline` 竞态清单  
- **IQ-42**：给 Cursor 的 backlog 表（ID / 风险 / 估时 / 依赖）

---

### IQ-45 — 收官

**写** `docs/phase0/iq17-closeout.md`：

- IQ-M1～M6 表（✅/❌/exception）  
- rubric 新分（诚实）  
- 未做项（B5、F 生产、5.5 差距）  
- 下一 Horizo​​n 建议（§15 或 §20.2 新行）

**更新** ISSUES #17 → `[x]` 或「Phase1 完成，D/F 待 Cursor」

---

## 6. 辅助脚本（可选）

在 `scripts/mimir_iq17_run_next.sh` 实现（与 `mimir_self_run_next.sh` 同构）：

- 解析 `MIMIR_TASK_QUEUE.md` §11 第一个 `[ ]`  
- 打印本文件 §5 对应小节标题  

Mimir 在 **IQ-07**（可并入 IQ-00）自实现该脚本；未实现前手动读表。

---

## 7. Cursor 复核包清单（刘哥恢复额度后）

| 优先级 | handoff ID | 说明 |
|--------|------------|------|
| P0 | PREREQ | `search_first_guard.py` + `agent_route_mixin.py` + `prompt_builder` 飞书禁令 |
| P0 | IQ-10 | prompt A |
| P1 | IQ-13 | AUTO_EVOLVE 默认（若拍板） |
| P1 | IQ-31 | WM B4 接线 |
| P1 | IQ-32～33 | Intent MVP 增强 |
| P2 | IQ-25 | brain_metrics 7d |

---

## 8. 风险与回滚

| 风险 | 缓解 |
|------|------|
| preemptive 每轮重复（PREREQ 前） | 先合 guard 修复再 IQ-15 |
| WM false positive 抑制 | B2 仅精确匹配；异常关 env |
| AUTO_EVOLVE 成本 | 观察 eval token；`.env` 可关 |
| Intent 误导 | 低置信 fallback；禁止 B5 |
| 飞书杀 gateway | 铁律见 §2 |

---

## 9. 给 Mimir 开场（刘哥复制到飞书）

```text
【IQ #17 · 按 Cursor 执行计划】
Read ~/src/MimirAether/docs/MIMIR_IQ17_EXECUTION_PLAN.md
TASK_QUEUE §11 第一条 [ ] 起，做到 IQ-45。
./scripts/mimir_iq17_run_next.sh --dry-run（有脚本则用）

铁律：
· 只认 §11 第一条 [ ]；做完立刻下一粒；禁止问「要不要继续」
· 未拍板 → 做 IQ-05 飞书表，跳过依赖 BLOCK 的粒
· [MIMIR_SKILL_ROUTE_NUDGE] → 先 skill_view
· 评估/进步 → self-audit + brain_metrics_snapshot
· 改 agent 后：tier0 绿 → push → bridge 写「Gateway 需刘哥 shell 重启」
· 飞书会话内禁止 ensure_single_gateway.sh

从 IQ-00 开始。
```

---

## 10. 修订日志

| 日期 | 摘要 |
|------|------|
| 2026-06-01 | Cursor 立案：§11 队列 + 本计划 + 拍板模板 + IQ-M1～M6 |
