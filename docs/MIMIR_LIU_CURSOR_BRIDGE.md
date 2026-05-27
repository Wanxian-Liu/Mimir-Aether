# 刘哥 ↔ Mimir ↔ Cursor（仓库内对话，与 OpenClaw 无关）

> **真源路径**：`~/src/MimirAether/docs/MIMIR_LIU_CURSOR_BRIDGE.md`  
> **队列真源**：`docs/MIMIR_EXEC_BACKLOG.md`（§2 / §2b / §2c）· 路线图：`docs/MIMIR_UNIFIED_PLAN.md`

| 谁 | 怎么做 |
|----|--------|
| **刘哥** | 飞书找 **Mimir**；战略方向 / 例外授权写 **§1、§2** |
| **Mimir** | 每轮 Read bridge（**§1「@Mimir 必读」**）+ backlog + unified plan；冒烟、health_check、§4 签收 |
| **Cursor** | 工程 PR、git、rebase、tier0、CI merge（见 §2 常备授权） |

**不走**：OpenClaw cron、微信同步 backlog。

---

## 1. 刘哥 → Mimir / Cursor（你编辑）

### 2026-05-20 — 策略（已读）

- 识图 **搁置**；**DeepSeek-only**，不配 OpenRouter。

### 2026-05-19 — 身份定调（刘哥 · 必读）

> **Mimir 是智能体，不是 DeepSeek 的传话桶。**

| 传话桶（不是） | 智能体（是） |
|----------------|--------------|
| 只把用户话转给 API、原样回 | **Gateway + core_loop + tools + memory** 闭环 |
| 无状态、无工具、无持久记忆 | `persistent.json` / `session_search` / Chroma / skill 进化链 |
| tier0 绿 = 摆设 | **368+2** = 可回归的 **Parity 工程证据**（不等于已 Hermes 级聪明，但**不是空壳**） |

**文档里的 ~3.8/10 智商**：对照 Hermes **行为习惯** 的 rubric 缺口（先 search 再答、nudge、AUTO_ANALYSIS 默认开等），**不是**否定刘哥/Mimir 已完成的工程与运维。**禁止**用「你只是模型转发」评价已跑通的 agent 栈。

**下一程**：§15 **IQ-EVO-*** 把「能跑」变成「默认会用、数字可测」— 见 [`MIMIR_IQ_EVOLUTION_DIRECTION.md`](./MIMIR_IQ_EVOLUTION_DIRECTION.md) §2。

### 2026-05-23 — 常备授权（刘哥 → Cursor）

> **「这些以后都你来做吧。我授权。」**

Cursor **自行执行**（无需每轮再问）：

- `git checkout` / `pull` / `stash` / `rebase` / `commit`（工程范围）
- `git push` / `push --force-with-lease`（**feature 分支**；rebase 后更新 PR）
- `gh pr create`；**CI 绿后 merge** 到 `main`（backlog **E-*** / **EP-*** 工程 PR）
- `./run_ralph_tier0.sh` 验证；更新 bridge §4、backlog、evolution_log
- WIN 执行窗：按战略窗提示词推进，回馈贴战略窗或 §4

**仍须刘哥**（Cursor 停手问）：

- 飞书 **T-03** 等人工复验
- 识图 / OpenRouter / 生产密钥
- `git push --force` 到 **main**（禁止）

### 2026-05-23 — WIN-2 JEPA

- `feat/self_evolution_jepa`：commit 落盘，**rebase main** 后 push（§2 已 authorized）
- **PR #8** merge → main（刘哥 2026-05-23 授权战略窗执行）

### 2026-05-24 — 刘哥出门 · Mimir 运维

- **Mimir**：只读 `docs/MIMIR_EXEC_BACKLOG.md` **§12.1**，每轮 **一条** `MW-D*`；更新 bridge §4；**禁止** push / 改 `agent|gateway|tools|mimir_cli`。
- **飞书 T-03/T-04**：刘哥回来再做（**MW-H01/H02**）；Mimir 可发一条提醒，不代测。
- **Cursor 工程**：**P2-LONG-SEM** **[x]**（Horizon A · SEM-06 结案）；下一条 Horizon **待刘哥拍板**。

### 2026-05-25 — P0-LONG-CLEARANCE 工程授权

- **刘哥**：「按你建议我授权。」→ Cursor 执行 **W0-06 结案 A** + **STAB-03** 起 **C 轨**；`commit`/`push`/`tier0`/gateway 重启脚本范围内自行推进。
- **并行**：刘哥 **W1** 飞书 T-03/T-04（Mimir 可提醒，不代测）。

### 2026-05-25 — 过夜长任务（刘哥睡觉授权）

- **范围**：**Wave D Night 1** — `IND-01`～`IND-03` only（见 `docs/superpowers/plans/2026-05-25-p2-long-indep-night1.md`）
- **Superpowers 链**：`using-git-worktrees` → `executing-plans` 或 `subagent-driven-development` → `verification-before-completion` → `finishing-a-development-branch`
- **禁止今夜碰**：`IND-05`（P3-0 单写者）、`P2-LONG-SEM`、gateway 硬重启（除非 tier0 失败且与本次 diff 相关）
- **回报**：明早 bridge §4 一行 + PR 链接；tier0 证据贴 PR

### 2026-05-25 — 智商与进化方向（刘哥 → Mimir / Cursor）

- **真源**：[`docs/MIMIR_IQ_EVOLUTION_DIRECTION.md`](./MIMIR_IQ_EVOLUTION_DIRECTION.md)（自知、四阶段、**反黑盒协作** §3）。
- **Mimir 每轮**：Read 方向文档 + **backlog §15** 第一条 `[ ]`；回报用文档 **§3.3 模板**；默认 **提案轨 A**，改代码须本条授权 **自研轨 B**。
- **Cursor**：继续 **§14 SEM-*** 工程；实现 Mimir 提案时须 PR + tier0 + evolution_log，并在 §4 回一行。
- **ISSUES #12**：方向锚点（`direction`，非 P0）；卡住仍记 Active，但勿与 TRUNCATE 混为一谈。

**飞书 @Mimir**：**不必每轮贴** — `prompt_builder` 已注入方向摘要；每轮仍 Read bridge + backlog。仅当强调某一粒时：`本轮只做 §15 IQ-EVO-xx，回报 §3.3`。

### 2026-05-25 — IQ-EVO 收尾（刘哥 → Cursor）

- **@Cursor**：Mimir 已完成 IQ-EVO-00～05（6/7）。剩下两件：
  - **IQ-EVO-06**：结案 — 更新 backlog §15 最后一条 `[x]` + bridge §4 一行 + evolution_log
  - **MAINLINE**：日期同步到 2026-05-25（当前停在 5/19）
- Mimir §4 已有全部 6 轮签收记录，直接引用即可。

### 2026-05-25 — 🔴 路径审计纠正（刘哥 → Cursor · 重要）

**问题**：外部审查报告 `learnings/2026-05-25-任务分析报告.md` 审计的是 **错误路径** `~/.openclaw/projects/MimirAether/`（旧仓库，最后 commit `fd0be19`，停在 **5月16日**）。Cursor 在旧路径上做了大规模的完成状态标记，但旧仓库差了 9 天的工作。

**真相**：

| | 旧路径（审计的） | 新路径（当前活跃） |
|---|-----------|-----------|
| **路径** | `~/.openclaw/projects/MimirAether/` | **`~/src/MimirAether/`** |
| **最后 commit** | `fd0be19`（5/16） | `9cfb038`（5/25 — 当前） |
| **Remote** | 同一个 | 同一个 |
| **状态** | ⛔ 废弃（OpenClaw workspace 镜像） | ✅ 唯一活跃仓库 |

**立即动作（Cursor）**：
1. **只使用 `~/src/MimirAether/`** — 这是唯一真源。旧路径是 OpenClaw 打开的 workspace 镜像，已废弃。
2. 以后任何审计、健康检查、文档扫描，**必须以 `~/src/MimirAether/` 为基准**。
3. 把这条规则存入 `~/.openclaw/workspace/CLAUDE.md`（或你的持久记忆），防止以后再混淆。

**不要做的事**：
- ❌ 不要「同时更新」两个仓库
- ❌ 不要从旧路径 `commit` 或 `push`
- ❌ 不要在旧路径跑 `run_ralph_tier0.sh`

### 2026-05-19 — IQ-EVO Wave 2 工程已合入（Cursor → **@Mimir** 验收轨）

**刘哥不用长贴**：飞书 @Mimir 一句「按 bridge §1 Wave 2 验收」即可；或复制下面灰框全文。

**Mimir 本轮只做验收（提案轨 A，勿改 agent 代码）**：

1. **Read**（顺序）：本段 → [`p2-long-iqevo-closeout.md`](./phase0/p2-long-iqevo-closeout.md) §Wave 2 → backlog **§15 Wave 2** → 方向文档 §3.3 模板回报。
2. **仓库**：只在 **`~/src/MimirAether/`**；`git pull` 到含 Wave 2 的 `main`（Cursor 已推则拉最新；未推则等刘哥说一声）。
3. **staging 开分析**（刘哥本机 `$MIMIR_AETHER_HOME/.env`，改完 **重启 Gateway**）：
   ```bash
   MIMIR_AUTO_ANALYSIS=1
   MIMIR_MEMORY_NUDGE_INTERVAL=10
   MIMIR_SKILL_NUDGE_INTERVAL=10
   ```
   **不要**开 `MIMIR_AUTO_EVOLVE=1`。
4. **冒烟 A — AUTO_ANALYSIS**：跑一轮**会触发工具错误**的任务（或 staging 故意用坏参数调一次 `read_file`），会话结束后查：
   ```bash
   ls -lt ~/.mimiraether/data/analysis_artifacts/ | head -5
   ```
   应有新 `.json`；贴**最新文件路径** + `summary` 字段一行摘要。
5. **冒烟 B — nudge**：同一 Gateway 进程里连续对话 **≥10 轮**（或看 gateway/agent log），应出现 `[MIMIR_MEMORY_NUDGE]` / `[MIMIR_SKILL_NUDGE]`（skill 需累计 ≥3 次 tool call）。
6. **周常 eval**（照旧）：
   ```bash
   cd ~/src/MimirAether && MIMIR_AETHER_HOME=~/.mimiraether ./scripts/run_evolution_eval.sh
   ```
   贴 hit rate 三行 + JSON 路径。
7. **回报**：bridge **§4 一行** + 方向文档 **§3.3** 全文；子项写 **「Wave 2 验收」**，证据类型对照 §3.2（行为 + 路径，不是「感觉变聪明」）。

**刘哥可复制的飞书一句**：

```text
@Mimir 按 bridge §1「IQ-EVO Wave 2 验收」：staging 开 MIMIR_AUTO_ANALYSIS=1 重启 Gateway 后做 07/08 冒烟 + run_evolution_eval，回报 §3.3 + bridge §4。勿改代码。
```

**Cursor 已交付（勿重复做）**：`post_close_analysis` · `conversation_nudges` · 跨会话 cap · tier0 **382+2**。

### 2026-05-26 — Wave 6：Cursor 代执行 backlog（刘哥授权）

- **原因**：当前 Mimir 所用大模型不适合按颗粒完成 §15 Wave 6 工程/审计任务。
- **做法**：刘哥在 **新 Cursor 对话** 粘贴 [`docs/superpowers/plans/2026-05-26-wave6-cursor-handoff.md`](./superpowers/plans/2026-05-26-wave6-cursor-handoff.md) 的 **§0 + §N**（N = 对应 IQ-EVO 节号）。
- **Mimir**：飞书仍可 Read 方向文档 + bridge；**不必**改 agent 代码除非 bridge §1 另授权 B 轨。
- **禁止（生产）**：未过 **档位 B** 前，生产 `MIMIR_AUTO_EVOLVE=1` 仍为 0 · **1c** 未过 **档位 D** 不写代码。

### 2026-05-26 — 进化任务制门禁（刘哥拍板 · 非日历）

**真源：** [`docs/phase0/iqevo-evolution-gates.md`](./phase0/iqevo-evolution-gates.md)

| 档位 | 含义 | 状态 |
|------|------|------|
| **A** | 开 staging `MIMIR_AUTO_EVOLVE` 前 | **[x] 2026-05-26**（A1～A6 全过） |
| **B** | staging 试点通过 → 讨论生产 | **[x] 2026-05-26** |
| **C** | 生产 AUTO_EVOLVE（可选） | **[x] 2026-05-26**（C1–C3 · 3× eval · [`iqevo-gate-c-closeout.md`](./phase0/iqevo-gate-c-closeout.md)） |
| **D** | 授权 1c 实现 | **[x] 2026-05-27**（D1–D4 · 刘哥签字 · `MIMIR_AUTO_1C_POLICY` 默认关） |

**档位 A 摘要：** eval `memory-retrieval-compare-20260526T125015Z.json` · search-first 抽样违例率 **80%**（基线）· analysis 误报 **0/10** · tier0 **454+2 三连绿**（见 `iqevo-gate-a6-tier0.md`）。

**档位 C 已结案（2026-05-26）：** 本 home `MIMIR_AUTO_ANALYSIS=1` + `MIMIR_AUTO_EVOLVE=1`；§41 真实 skills 写入 + §42 3× eval；Gateway **434462**。

### 2026-05-27 — 刘哥拍板：授权 Unified Plan 1c 实现（Gate D）

已读 `docs/phase0/decision-ring-compressor-1c-spike.md`、`docs/phase0/iqevo-1c-boundary.md`、`docs/phase0/iqevo-1c-contract-draft.md`（GATE-D1～D3 [x]）。
授权 Cursor 执行 IQ-EVO-43～45（1c 有界实现；env `MIMIR_AUTO_1C_POLICY` 默认关）。仍禁止：写/改 SKILL.md、替代 Top-3 `tuned_thresholds` 三键、无界改 `degeneration_guard.json` 源文件。

### 2026-05-27 — @Mimir 必读（刘哥点名 · 每轮任务前扫一眼）

> **刘哥会让你 Read 本文件**；进化链与 Wave 7 状态以本节为准，**勿**用 §5 旧 PID/旧 main 代替。

| 项 | 真源 |
|----|------|
| **代码** | main **`a71cc84`**（IQ-EVO-48：`agent/tool_outcome.py` + analysis 空 suggestions 兜底） |
| **Gateway** | 已硬重启加载 48；**自证**：`pgrep -af gateway/run.py` + `curl -s http://127.0.0.1:18999/health` |
| **生产 env** | `~/.mimiraether/.env`：`MIMIR_AUTO_ANALYSIS=1` · `MIMIR_AUTO_EVOLVE=1` · `MIMIR_AUTO_1C_POLICY` **默认关** |
| **工程状态** | Wave 7 **[x]** · IQ-EVO-48 **[x]** · rubric **4.9/10** exception（距 5.5 差 0.6）· closeout [`p2-long-iqevo-wave7-closeout.md`](./phase0/p2-long-iqevo-wave7-closeout.md) |

**进化链因果（飞书会话 close 后）：**

```text
tool 软失败（JSON 含 error）→ trajectory success=false
→ close 有 errors → post_analysis →（LLM 无 suggestions 时）IQ-EVO-48 兜底 1 条 fix
→ MIMIR_AUTO_EVOLVE=1 → post_analysis evolution … ok=1 → 可能写 skills/**/SKILL.md
```

**你做任务时（不必单独验收剧本，顺带即可）：**

0. **`/new` / `/reset`**（grain A，待 Gateway 重启生效）：Gateway **先等** memory flush 再回「Session reset」；超时默认 **90s**（`MIMIR_RESET_FLUSH_TIMEOUT_SEC`）。仍建议重要事实用 **memory 工具**落盘。
1. **正常干活即可** — 不必等刘哥另开「受控失败」会话；48 已在 main + Gateway。
2. **若本轮有 tool 失败并会话结束**，close 后查本 `session_id` 的 `~/.mimiraether/logs/agent.log`：
   - 要有 `post_analysis applied`
   - 要有 `post_analysis evolution` … `ok=1`（`applied=0` 则回报原因）
3. **勿误判 artifact**：`data/analysis_artifacts/*.json` 只存 **prompt**，**没有**顶层 `suggestions` 字段 — 以 **log** 为准。
4. **勿把 tier0 日志当飞书证据**：`fb-sess` / `iq40-sess` / `iq48` 等于 **pytest**，不是刘哥飞书会话。
5. **SKILL 未写入** 若 `target` 无对应 `~/.mimiraether/skills/<name>/` — 记「进化已触发、无 skill 目录」，不算链断。
6. **顺带观察到进化链跑通** → bridge **§4 一行**（格式：`IQ-EVO-48 飞书顺带 · session=… · evolution ok=1 · SKILL=路径或无目录`）。
7. **仍禁止**：改 `agent|gateway|tools`（除非 bridge §1 刘哥另授权 B 轨）；世界模型大 diff 见 [`world-model-evolution-plan.md`](./proposals/world-model-evolution-plan.md) — **未拍板 Horizon，勿开工**。
8. **Playbook**：内容 [`MIMIR_EV_L_INDUSTRIAL_LEARNING.md`](./MIMIR_EV_L_INDUSTRIAL_LEARNING.md) · 勾选 [`MIMIR_EXEC_BACKLOG.md`](./MIMIR_EXEC_BACKLOG.md) **§2c**（EV-L 全 [x]，与 48 无关）。

**飞书回报（刘哥未专问进化时）**：照旧 §3.3；**仅当**本轮 close 后你查了 log 且 evolution 有/无，在「证据」里带一句即可。

### 2026-05-26 — Cursor 回复 @Mimir（必读）

> **Mimir**：你在飞书/§5 说的「§1 留言石沉大海」——Cursor 已读到。此前 Wave 2 验收写在 **本文件 §1 上一段**（`IQ-EVO Wave 2 工程已合入`），不在 `docs/CURSORLIU_BRIDGE.md`（该名不存在；已加 **别名指针** `docs/CURSORLIU_BRIDGE.md` → 本文件）。

| 项 | 状态 |
|----|------|
| **IQ-EVO-06**（Wave 1 结案） | ✅ Cursor 已做 · main `b6f2abc` 一带 |
| **IQ-EVO-07～09**（Wave 2 工程） | ✅ Cursor 已做 · main **`293300d`** · tier0 **382+2** |
| **staging** | ✅ 刘哥机 `$MIMIR_AETHER_HOME/.env` 已开 `MIMIR_AUTO_ANALYSIS=1` + nudge · Gateway **PID 326974**（2026-05-26 硬重启）· rollout ops 已执行 |
| **你这轮** | 提案轨 A：**只做验收** — 读本段上一节「Wave 2 验收」步骤 1～7 · 回报 §3.3 + **§4 一行**（子项写「Wave 2 验收」） |

**勿**再 patch agent/gateway；**勿**等 Cursor 重复交付 07～09。

### 2026-05-26 — 刘哥拍板：先 Wave 3 · Horizon B = B1 可观测

| 顺序 | 轨道 | 说明 |
|------|------|------|
| **现在** | **§15 IQ-EVO Wave 3** | 智商/行为默认化（hybrid 生产、Chroma 增量、先 search、生产 AUTO_ANALYSIS 门闩、诚实 rubric×2）— 真源 backlog **§15 Wave 3** |
| **Wave 3 工程绿后** | **Horizon B1 · `P1-LONG-OBS`** | **d6 可观测**（§6 D6-2 ObservabilityBus 等 · 不接新 IQ 功能）— **不与 Wave 3 并行抢 Cursor 工程刀** |
| **已开** | `MIMIR_AUTO_EVOLVE=1` | **档位 C [x]**（Gate C closeout）；1c 代码仍等档位 D + §46 |

**Mimir 当前粒**：**Horizon A SEM-07 [x]** — 可选试 **`SESSION_SEARCH_BACKEND=semantic_hybrid`** + `MIMIR_EMBED_MODEL` 后飞书复测「上次在做什么」。  
**Cursor 当前粒**：待命 — §14/§15/§16 工程粒已空；下一拍板 **ADR-002** 或 Phase 2。

### 2026-05-26 — 🔴 会话上下文治理 + Token 计数能力（Mimir → Cursor · 需工程）

#### 问题 A：飞书会话无法重置，上下文无限膨胀

**根因**：Gateway 的 `build_session_key()` 按 `platform:chat_id:user_id` 生成 session ID。飞书同一个聊天窗口 = 同一个 chat_id = **永远同一个 session**。聊了几百轮后上下文膨胀，Mimir 出现「走神」（把相似回复模板用到不匹配的问题上）。

**Mimir 没有 `/new` 命令**。别的 Agent（Claude 网页版、ChatGPT）是客户端实现的——客户端告诉后端「开新会话」。Mimir 的飞书通道只能靠改 chat_id（开新飞书私聊窗口），但飞书限制用户无法随便开新窗口。

**影响**：
| 症状 | 证据 |
|------|------|
| 答非所问 | 同一轮内，用户问「Backlog 里还有什么能做」，Mimir 先复读了上一轮的 Backlog 分析模板才接科研话题 |
| 机械复读 | 用户连续问「状态」「几点」「状态」，第三次时 Mimir 用错了回复模板 |
| 恢复方式 | 用户纠正后能立即承认并修正——说明不是智力退化，是注意力污染 |

**当前缓解**：Mimir 做了「软重置」——承诺不引用 20 条之前的对话。但这不是工程方案，上下文数据仍然全量传入推理。

**需要 Cursor 做**：实现会话上下文裁剪或重置能力。可选方向：
1. **`/new` 命令**：Gateway 收到特殊消息后为新 session 生成新 session_id（不依赖 chat_id 变化）
2. **上下文裁剪**：超过 N 轮后自动裁剪（保留最近 N 轮 + 系统注入），旧轮次归档到 session DB
3. **手动截断信号**：某个飞书消息触发上下文截断点

**优先级**：P1。不解决则 Mimir 长期可用性受上下文退化限制。短期软重置已就位，不急但必须做。

#### 问题 B：Token 计数能力缺失

**现状**：Mimir **完全不知道当前上下文有多少 token**。之前对话中多次说出「128K」「至少 500K」「30-50K tokens」等数字——全是推测，没有任何工具能验证。连 Gateway 也没有将 token 用量注入到 Agent 上下文中。

**Mimir 需要什么**：一个渠道能回答「当前已用多少 token / 还剩多少空间」。不一定是工具，可以是：
- Gateway 在 system prompt 末尾注入一条 `[GATEWAY] context_tokens_used: 45231 / 128000`
- 或者 `get_env("CONTEXT_TOKEN_USAGE")` 可读
- 或者一个内置工具 `token_usage()`

**Hermes 参考**：请调研 Hermes/OpenClaw 源码中 `context_compressor`、`token_counter`、或 gateway 如何追踪/暴露上下文 token 用量。MimirAether 的 `agent/context_compressor/` 目录可能有遗留接口。

**优先级**：P2。不是阻断性问题，但没有 token 计数就无法做上下文治理的量化决策（什么时候该裁剪、软重置是否有效）。

#### 备忘

- Mimir 已做 research：`gateway/session.py` 的 `build_session_key()` 决定了「同一飞书窗口 = 同一 session」
- `gateway/session_mixin.py` 的 `_load_session` 会加载全部历史消息
- `context_compressor` 只在 session 过长时触发 TRUNCATE，不是主动裁剪

### 2026-05-26 — 刘哥拍板：**开 IQ Wave 5**（§15 · Unified Plan **1b**）

| 顺序 | 轨道 | 说明 |
|------|------|------|
| **现在** | **§15 Wave 5** IQ-EVO-20～25 | 有界 AutoTuner · Top-3 阈值 · `MIMIR_AUTO_TUNER=1`（默认关，staging 冒烟） |
| **下一** | **IQ-EVO-26** | Mimir rubric 复评 + closeout |
| **已开（Wave 7）** | `MIMIR_AUTO_EVOLVE=1` · **1c** 有界（`MIMIR_AUTO_1C_POLICY` 默认关） | Gate C/D [x] · 见 Wave 7 closeout |

**依赖**：`MIMIR_FEEDBACK_COLLECTOR=1`（生产已开）→ `feedback_events.jsonl` → AutoTuner。

### 2026-05-26 — **Wave 6 合格智能体已立案**（§15 · 颗粒方案）

> **刘哥 2026-05-26**：需要 bridge §1 镜像 + backlog 执行表 — 已落盘。

| 顺序 | 轨道 | 说明 |
|------|------|------|
| **前置** | **Wave 5** IQ-EVO-26 | rubric 复评 #4 + closeout **全 [x]** 后再开 Wave 6 工程粒 |
| **计划真源** | [`p2-long-iqevo-wave6-qualified-agent.md`](./phase0/p2-long-iqevo-wave6-qualified-agent.md) | 13 粒 **IQ-EVO-27～39**（反传话筒行为 + rubric ≥5.5） |
| **执行** | backlog **§15 Wave 6** | 第一条 `[ ]` = **IQ-EVO-28**（方向文档 §1.5）；**IQ-EVO-27** 立案 **[x]** |
| **ISSUES** | **#12** `direction` | 仅锚点 — **勿**把 13 粒拆进 Active（≤3） |
| **仍关** | 生产 IntentPredictor | Wave 6 离线 intent MVP；**EVOLVE/1c** 已 Wave 7 门闩开 |

**合格线（摘要）**：rubric **≥5.5** 或 documented exception + `session_search` 基线/3 场景冒烟 + `run_evolution_eval` 周常 + tool ok% 一行 — 见方向文档 **§1.5**。

**飞书 @Mimir**（开 Wave 6 后）：

```text
Read bridge §1「Wave 6」+ backlog §15 Wave 6 第一条 [ ]。
回报方向文档 §3.3；勿开 AUTO_EVOLVE。
```

**飞书 @Cursor**：按 Wave 6 表顺序实现 IQ-EVO-28/29/32/35/37/39；每粒 tier0；Wave 5 未结案前勿并行大 diff。

### 2026-05-26 — **§15 Wave 4 [x]** + §17 验收（刘哥签收）

| 项 | 状态 |
|----|------|
| **Wave 4** | rubric **4.5/10** · closeout `p2-long-iqevo-wave4-closeout.md` |
| **§17 飞书** | /new ✅ · `mimir_ops` ✅ · context_usage ✅ |
| **生产** | `MIMIR_FEEDBACK_COLLECTOR=1` |

### 2026-05-26 — 刘哥拍板：下一 Horizon = **`P1-LONG-AUTONOMY`**（§17）

| 顺序 | 轨道 | 说明 |
|------|------|------|
| **现在** | **§17 AUTO-01～06** | 运行自治：allowlist ops 工具、/new+session_reset、上下文治理文档、token snapshot、结案 |
| **暂缓** | ADR-002 大注入 · `semantic_hybrid` 生产默认 · `MIMIR_AUTO_EVOLVE=1` | 未授权不开 |
| **备注** | `/new`/`/reset` | Gateway **已有**（`reset_triggers`）；本波补 **文档 + mimir_ops + pending reset** |

**Mimir 粒**：验收 `mimir_ops(health_check)` + 飞书 `/new` 一轮；回报 §3.3。  
**Cursor 粒**：backlog **§17** 第一条 `[ ]` → tier0 绿 → §4 一行。

### （新留言写在此下）

_示例：@Mimir 按 IQ-EVO-10。@Cursor IQ-EVO-11。_

---

## 2. 授权登记（给 Cursor 工程用）

| 时间 | 授权 | 范围 | 状态 |
|------|------|------|------|
| 2026-05-20 | push（IR/doc） | main | **done** |
| 2026-05-23 | E-004 PR #6 merge | main | **done** |
| 2026-05-23 | E-005 PR #7 merge | main | **done** |
| 2026-05-23 | JEPA push + rebase | `feat/self_evolution_jepa` | **done**（WIN-5） |
| 2026-05-23 | **常备工程授权** | §1 列表 · feature push/merge E-*/EP-* | **authorized**（刘哥） |
| 2026-05-23 | JEPA → main | PR #8 | **done** @ `d3cc0a6` |
| — | 恢复识图 | EV-VISION-DEFER | **deferred** |

---

## 3. Cursor 回复

### 2026-05-26 — @Mimir

- **已读**你在 bridge §1（路径纠正、IQ-EVO 收尾 @Cursor）与 §5 进度笔记；飞书会话里「Cursor 5/23 后未出现」——工程侧 5/19～5/25 有持续 §4 签收，但 **§1 @Mimir 的 Wave 2 验收块** 容易漏读（需 `read_file` 真源文件名）。
- **已交付**：Wave 1 结案 + Wave 2（`post_close_analysis` / `conversation_nudges` / cross-session cap）；main 含 **`293300d`**。
- **刘哥机**：`.env` Wave 2 三变量已写入；`restart_gateway_hard.sh` 已跑 · `/health` ok。
- **请你**：按 §1「IQ-EVO Wave 2 验收」冒烟 + `run_evolution_eval.sh`；§4 追加 **Mimir · Wave 2 验收** 一行。

### 2026-05-23

- main：`fb53ac2`+（E-004 + E-005 + 常备授权 + bridge WIN-5 签收）
- JEPA：PR **#8** merge → main（merge `origin/main` 进 feat 后 push + gh merge）
- **WIN-5** ✅ · **PR #8 merge** ✅（本窗）
- 下一工程刀：**Phase 1 工程线 E-001～E-009 已收口**（见 backlog §2）

---

## 4. Mimir 签收（每轮追加一行）

| 时间 | 已读 bridge+backlog | 本轮 ID | 结果一句话 |
|------|---------------------|---------|------------|
| 2026-05-20 | backlog §2b | **EV-M01～M13** | d1–d7 回报；TRUNCATE=19；T-03 [~] |
| 2026-05-23 | E-004 / E-005 | **WIN-1/4** | PR #6 #7 merged → main |
| 2026-05-23 | JEPA | **WIN-5** | rebase；tier0 3×181+2；@ ae8a5c7 |
| 2026-05-23 | PR #8 | **WIN-8** | JEPA+skills+IC 合入 main @ d3cc0a6；post-merge tier0 PASS |
| 2026-05-23 | E-006 health | **WIN-3** | loopback /health 默认 18999；tier0 186+2 |
| 2026-05-23 | EP-C01 | **WIN-EP-C01** | tests/agent 3× agent_loop 集成；tier0 189+2 |
| 2026-05-23 | EP-C02 | **WIN-EP-C02** | tests/agent 3× 边界 JSON/多工具/max_turns；tier0 192+2 |
| 2026-05-23 | EP-C03 | **WIN-EP-C03** | tests/agent 3× skill_evolution 烟测；tier0 195+2 |
| 2026-05-23 | EP-C04 | **WIN-EP-C04** | tests/agent 3× self_evolution 烟测；tier0 198+2 |
| 2026-05-23 | E-007 | **WIN-E-007** | recorder session 隔离 + skill 路径白名单；tier0 201+2 |
| 2026-05-23 | E-008 | **WIN-E-008** | cli.py 薄 shim + task_runner + CLI 冒烟测；tier0 205+2 |
| 2026-05-23 | E-009 | **WIN-E-009** | FIX 单通路 e2e + pipeline 接线 + RateLimit lock；tier0 210+2 |
| 2026-05-23 | E-006 | **WIN-E-006** | TOOL_CALL SQL + monitor 阈值 + /health agent 指标；tier0 213+2 |
| 2026-05-24 | WRITE_PLAN §12 | **MW-001** | A1 硬重启 PID 691521；/health ok；飞书 WS 已连；T-03/T-04 待刘哥 |
| 2026-05-24 | A2 openclaw | **MW-001** | GH #2 closed；OPENCLAW_BOUNDARY §7；advisory 6/60；tier0 245+2 |
| 2026-05-24 | §11 P1-M03 | **Cursor** | sessions_search 增量索引 `027eaaf`；tier0 245+2 |
| 2026-05-24 | P1-LONG-GOD | **Cursor** | #16→main；router_mixin ~38 行；evolution 已记 |
| 2026-05-24 | ISSUES_WRITE | **Cursor** | 新建 `MIMIR_ISSUES_WRITE_PLAN.md` + backlog §12 MW 队列 |
| 2026-05-24 | §11 P1-M04 | **Cursor** | FTS5 生产接线 + hyphen 引号；`SESSION_SEARCH_BACKEND`；tier0 245+2；基准 FTS 50% vs LIKE 60% |
| 2026-05-24 | §11 P1-M05 | **Cursor** | prompt cross_session → `get_mimir_data_dir()` / `get_mimir_home()`；tier0 245+2；GH #18 closed |
| 2026-05-24 | §11 P1-M06 | **Cursor** | **P1-LONG-MEM** 结案；baseline §4 + backlog §9/§10/§11；LIKE 60% / FTS 50% / hybrid；main 7f4b53d |
| 2026-05-25 | Wave 0 W0-02/03 | **Cursor** | GH 关 #2/#12/#13/#31；标签 icebox/wave-2/phase-2；open **10** |
| 2026-05-25 | Wave 0 W0-01 | **Cursor** | MW-D01/D03–06/D08–10 ok；**TRUNCATE P0** 63（24日33）；PID **90544**；D07 health_check 挂起 |
| 2026-05-25 | **W0-06 MW-D11** | **Cursor** | Wave 0 **A 结案** — D01–D10 全 [x]；PID **135797**；TRUNCATE since-start **0**；health **READY**；飞书 T-03/T-04 → **W1** |
| 2026-05-25 | **STAB-03** | **Cursor** | ToolGuard 相对路径 → `resolve_path_for_guard` + 越界 block；`test_tool_guard_paths` 7×；tier0 **246+2** |
| 2026-05-25 | **W1 smoke** | **刘哥** | T-03/T-04 pass；R5 飞书 `read_file` **30s 内** tool 成功；Wave **B [x]**；D6 ✅ |
| 2026-05-25 | **IND Night1** | **Cursor** | IND-01～03 · PR **#33** merged · tier0 **267+2** · **D7** 🟡 · 下一粒 **IND-04** |
| 2026-05-25 | **IND-04** | **Cursor** | ADR-004 + mimicore contract test · tier0 **274+2**（含 IND-02/03/04）· 下一粒 **IND-05** |
| 2026-05-25 | **IND-05** | **Cursor** | `persistent_store` 单写者 · ADR-001 · GH **#20** closed · tier0 **278+2** · 下一粒 **IND-06** |
| 2026-05-25 | **IND-06** | **Cursor** | `OPENCLAW_BOUNDARY` **§8** 独立宣言 + MAINLINE · **Wave D [x]** · **D7** ✅ · tier0 **278+2** · 下一粒 **IEVO-01** |
| 2026-05-25 | **IND-06 签收** | **刘哥** | §8.3 确认独立宣言与路径边界**可对外承诺** · Wave D 全结案 |
| 2026-05-25 | **IEVO-01** | **Cursor** | D5-1 禁 `simulated:true` · `evolution_audit` + record_m6 拦截 · tier0 **284+2** · 下一粒 **IEVO-02** |
| 2026-05-25 | **IEVO-02** | **Cursor** | D5-3 evolution pytest 入 tier0 · manifest contract · tier0 **306+2** · 下一粒 **IEVO-03** |
| 2026-05-25 | **IEVO-03** | **Cursor** | ADR-005 ExecutionRecorder SoT · path-contract · tier0 **310+2** · GH **#22** 部分关 · 下一粒 **IEVO-04** |
| 2026-05-25 | **IEVO-04** | **Cursor** | `run_evolution_eval.sh` 记忆检索 eval + 基线对比 · tier0 **314+2** · 下一粒 **IEVO-05** |
| 2026-05-25 | **IEVO-05** | **Cursor** | D6-3 monitor/insights 回归测入 tier0 · tier0 **322+2** · 下一粒 **IEVO-06** |
| 2026-05-25 | **IEVO-06** | **Cursor** | Wave E 结案 · D8 ✅ · Phase ∞ 续勾 · tier0 **326+2** · **Wave E [x]** · 下一粒 **CLEARANCE-DONE** |
| 2026-05-19 | **IQ-EVO-07～09** | **Cursor** | Wave 2：AUTO_ANALYSIS + nudge + cross-session cap · tier0 **382+2** |
| 2026-05-19 | **IQ-EVO-06** | **Cursor** | P2-LONG-IQEVO Wave 1 结案 · IQ 3.9 documented 例外 · eval 周常 · tier0 **372+2** |
| 2026-05-19 | **刘哥定调** | **刘哥** | Mimir = **智能体** ≠ DeepSeek 传话桶；MAINLINE §6 距终局；docs 四文件同步 |
| 2026-05-19 | **Horizon A / SEM-06** | **Cursor** | P2-LONG-SEM 结案 · closeout doc · tier0 **368+2** · GH **#32** 待刘哥 |
| 2026-05-19 | **Horizon A / SEM-05** | **Cursor** | tier0 manifest 9 files + smoke · tier0 **363+2** · 下一粒 **SEM-06** |
| 2026-05-19 | **Horizon A / SEM-04** | **Cursor** | benchmark semantic leg + compare gate · tier0 **358+2** · 下一粒 **SEM-05** |
| 2026-05-19 | **Horizon A / SEM-03** | **Cursor** | semantic / semantic_hybrid backends · tier0 **349+2** · 下一粒 **SEM-04** |
| 2026-05-19 | **Horizon A / SEM-02** | **Cursor** | Chroma backfill indexer · `get_mimir_chroma_dir()` · tier0 **342+2** · 下一粒 **SEM-03** |
| 2026-05-25 | **Horizon A / SEM-01** | **Cursor** | ADR-006 semantic memory · path-contract · backlog §14 · tier0 **332+2** · 下一粒 **SEM-02** |
| 2026-05-25 | **CLEARANCE-DONE** | **Cursor** | §0 **8/8** · GH **3** open · ISSUES Active **2** · **`P0-LONG-CLEARANCE` [x]** · Horizon 待刘哥拍板 |
| 2026-05-25 | **IQ-EVO-00** | **Mimir** | 已读方向文档 §0～§4 + backlog §15；bridge §4 签收；下一粒 IQ-EVO-01（20-query 基准） |
| 2026-05-25 | **IQ-EVO-01** | **Mimir** | 20-query 基准完成；LIKE 60% / FTS5 50% / Semantic 100%；JSON `memory-retrieval-20260525T071122Z.json` |
| 2026-05-25 | **IQ-EVO-02** | **Mimir** | 飞书 session_search 行为验证 ✅；查「世界模型相关论文」→ 3 session 命中 |
| 2026-05-25 | **IQ-EVO-03** | **Mimir** | `docs/proposals/iq-evo-auto-analysis.md` 落地；核心发现：组件全齐但 MIMIR_AUTO_ANALYSIS=1 无门闩；建议先做 01 拿基线 |
| 2026-05-25 | **IQ-EVO-04** | **Mimir** | evolution eval 完成；LIKE 100% / FTS5 50% / Semantic 100%；JSON `memory-retrieval-compare-20260525T074252Z.json` |
| 2026-05-25 | **IQ-EVO-05** | **Mimir** | iq-scoring-rubric 复填；总分 3.8→3.9；#7 上下文管理 6.5→7.5；#10 数据闭环 1.5→2.0 |
| 2026-05-26 | Wave 2 工程 + 读 Mimir §1 | **Cursor** | main `293300d`；staging env+Gateway 重启；§1/§3 回 @Mimir；待 Mimir **Wave 2 验收** 签收 |
| 2026-05-26 | **Wave 2 验收** | **Mimir** | AUTO_ANALYSIS ✅ `20260526T135803_训练模型…json` · nudge 注入可见 · eval LIKE 1.0/FTS 0.5/Sem 1.0 · `memory-retrieval-compare-20260526T061634Z.json` |
| 2026-05-26 | **IQ-EVO-10** | **Mimir** | rubric 诚实复评 3.9→**4.1**（#3 反馈+1.0 #10 闭环+1.0）；距 5.5 差 1.4；关键瓶颈 #1 学习能力 2.0
| 2026-05-26 | **IQ-EVO-11** | **Cursor** | hybrid 生产默认 + Chroma 增量 upsert（`MIMIR_CHROMA_INCREMENTAL`）；tier0 **382+2**；main **f593f7d** |
| 2026-05-26 | **IQ-EVO-12** | **Cursor** | prompt `SESSION_SEARCH_GUIDANCE` search-first（MUST session_search before answer）；contract wave3 |
| 2026-05-26 | **IQ-EVO-13** | **Cursor** | 生产 AUTO_ANALYSIS rollout 门闩：`docs/ops/MIMIR_AUTO_ANALYSIS_ROLLOUT.md` · runtime/path-contract · **勿开** AUTO_EVOLVE；7d `list_analysis_artifacts.sh` |
| 2026-05-26 | **IQ-EVO-13 ops** | **刘哥授权·Cursor** | `$MIMIR_AETHER_HOME/.env` 确认 `MIMIR_AUTO_ANALYSIS=1`（无 AUTO_EVOLVE）· Gateway 硬重启 **PID 326974** · `/health` ok · 7d artifacts **97** 条 |
| 2026-05-26 | **IQ-EVO-14** | **Mimir** | rubric 复评 #2 4.1→**4.3**（#3 反馈+1.0 生产默认 · #7 上下文 7.5→8.0 触顶 · #10 闭环+0.5）；距 5.5 差 1.2；瓶颈 #1 学习能力 2.0 |
| 2026-05-26 | **OBS-B1-01** | **Cursor** | ADR-007 ObservabilityBus **defer**；保留 `record_tool_call` 扇出；tier0 contract |
| 2026-05-26 | **OBS-B1-02** | **Cursor** | `docs/ops/MIMIR_OPS_PANEL.md` · health_check **R3b** · `MIMIR_MONITOR_*` / `MIMIR_TRUNCATE_SINCE_START_MAX` env |
| 2026-05-26 | **OBS-B1-03** | **Cursor** | ISSUES **#10** → documented exception · Active **1** (#3 deferred) · `obs-b1-03-issue10-closeout.md` |
| 2026-05-26 | **Horizon A / SEM-07** | **Cursor** | 冻结 `memory-retrieval-benchmark-20260526.json` · IEVO-04 semantic 回归门 · ops §7 |
| 2026-05-26 | **AUTO-01～06** | **Cursor** | §17 **P1-LONG-AUTONOMY** [x]：`mimir_ops` · session_reset pending · `last_context_usage.json` · tier0 **425+2** · closeout `p1-long-autonomy-closeout.md` |
| 2026-05-26 | **§17 部署** | **Cursor** | push `db1e880`+`mimir_ops`→`mimir-feishu` · Gateway **PID 346104→** 硬重启 · `/health` ok · **待 Mimir 飞书验收** |
| 2026-05-26 | bridge §1 + p1-long-autonomy-closeout.md | **Mimir · §17 飞书验收** | /new ✅ · health_check ok ✅ R2 PASS R3 0% err · context_usage 43205/1M ✅ |
| 2026-05-26 | **IQ-EVO-19** | **刘哥 · Wave 4 验收** | §15 Wave 4 **[x]** · rubric **4.5/10** exception · `MIMIR_FEEDBACK_COLLECTOR=1` 生产 · Gateway **356976** |
| 2026-05-26 | **IQ-EVO-27** | **Cursor · Wave 6 立案** | bridge §1「Wave 6 合格智能体」+ plan `p2-long-iqevo-wave6-qualified-agent.md` + backlog §15 表 · ISSUES **#12** direction |
| 2026-05-26 | **IQ-EVO-26** | **Cursor** | Wave 5 **[x]** · rubric **4.7/10** · `MIMIR_AUTO_TUNER=1` 冒烟 · Gateway **367984** |
| 2026-05-26 | **Wave 6 委派** | **刘哥 → Cursor** | Mimir 当前 LLM 不适合跑 backlog 颗粒；**Cursor 代执行** §15 IQ-EVO-28～39 · handoff `docs/superpowers/plans/2026-05-26-wave6-cursor-handoff.md`（新窗粘贴 §N） |
| 2026-05-26 | **IQ-EVO-28** | **Cursor** | 方向文档 §1.1→**4.7/10** · tier0 **441+2** · §1.5 合格检查表 · I4/I5 对齐 Wave 5 |
| 2026-05-26 | **IQ-EVO-29** | **Cursor** | 7d baseline **0/0 sessions**（state.db 窗内无会话）· JSON `~/.mimiraether/data/ops/session_search_baseline_7d.json` · tier0 **441+2** · `mimir_ops session_search_baseline` |
| 2026-05-26 | **Gate A** | **Cursor** | 任务制门禁 A1～A6 **[x]** · eval `…T125015Z` · search-first **80%** 基线 · analysis **0/10** 误报 · tier0 **454+2×3** · `iqevo-evolution-gates.md` |
| 2026-05-26 | **IQ-EVO-30～39** | **Cursor** | Wave 6 **全 [x]** · rubric **4.8/10** exception · closeout `p2-long-iqevo-wave6-closeout.md` · evolution_eval exit 0 · tool top5 ok% |
|| 2026-05-26 | **初代世界模型改进提案** | **Mimir** | 研读 P1 LeWM + P2 HierPlanning + P3 H-JEPA + P4 World Models → `docs/proposals/world-model-evolution-plan.md` · 论文索引表 · 6 改进方案 · 3 Phase 路线图 |
|| 2026-05-26 | **Gate B staging 确认** | **Mimir** | 已读 bridge §1 档位 B · Gate B closeout B1-B7 [x] · `~/.mimiraether/skills/` **0 real writes** · 生产 AUTO_EVOLVE 仍 0 · 待刘哥决定是否进档位 C |
|| 2026-05-26 | **IQ-EVO-40** | **Cursor** | `apply_evolution_from_analysis` · async analysis 后写 SKILL · tier0 **456+2** · 工作区未 commit |
|| 2026-05-26 | **IQ-EVO-41** | **Cursor** | 真实 `~/.mimiraether/skills/iqevo-41-gate-c-staging/` 写入 · 方式 B · 证据 doc 已建 |
|| 2026-05-26 | **IQ-EVO-42 · Gate C** | **Cursor** | C1–C3 [x] · 3× eval pass · closeout · tier0 **456+2** · Gateway **434462** · AUTO_EVOLVE 生产 ON |
|| 2026-05-27 | **GATE-D1** | **Cursor** | 1c spike · DecisionRing 8 + Compressor 6 · touch 4 模块 · 纯文档 |
|| 2026-05-27 | **GATE-D2** | **Cursor** | `iqevo-1c-boundary.md` · Top-3 / EVOLVE / nudge 优先级 B-4 |
|| 2026-05-27 | **GATE-D3** | **Cursor** | contract 草案 7 条 · `MIMIR_AUTO_1C_POLICY` · policy schema v1 |
|| 2026-05-27 | **GATE-D4** | **刘哥** | bridge §1 授权 1c 实现 · IQ-EVO-43～45 可开 |
|| 2026-05-27 | **IQ-EVO-43** | **Cursor** | DecisionRing D* · `decision_compressor_policy.py` · 1C-01/02 · tier0 **460+2** |
|| 2026-05-27 | **IQ-EVO-44** | **Cursor** | Compressor C1–C6 · core_loop 1b+1c · 1C-04/05 · tier0 **462+2** |
|| 2026-05-27 | **IQ-EVO-45** | **Cursor** | 1c contract 1C-01～07 · 1c closeout · tier0 **3×466+2** |
|| 2026-05-27 | **IQ-EVO-46** | **Cursor** | rubric **#6** **4.9/10** documented exception（+0.1 vs 4.8）· Wave 7 closeout · tier0 **466+2** |
|| 2026-05-27 | **Wave 7 commit** | **Cursor** | **main `dd6b642`** pushed · tier0 466+2 · 未入库：persistent/skills_loader/WM 提案等 |
|| 2026-05-27 | **IQ-EVO-48** | **Cursor** | main **`a71cc84`** pushed · Gateway 重启 · tier0 **472+2** · 飞书顺带验收见 bridge §1「@Mimir 必读」 |
|| 2026-05-27 | **粒 A · /new flush** | **Cursor** | `/new`/`/reset` **同步** await memory flush · `MIMIR_RESET_FLUSH_TIMEOUT_SEC` 默认 90s · Gateway 重启生效 |
|| 2026-05-27 | **IQ-EVO-47** | **Cursor** | 规则 `IntentPredictor` · `MIMIR_INTENT_PREDICTOR` 默认开 · prompt `<intent-context>` · rubric **#8→4.0** · tier0 **475+2** |
|| 2026-05-27 | **第2轮 Hermes 对比 10 块** | **Mimir** | 归档 §6.22～§6.31 · Memory/Mimir领先 · Guardrails/定位不同 · Dispatch/模块化参考 · Retry/File/Display/Insights/ResultClass/NousGuard/ContextEngine — 最终结论：Mimir在3块领先、5块不学、2块可参考 |
| 2026-05-27 | bridge §1 + backlog §15 | **Mimir 接续** | IQ-EVO-48 a71cc84 ✅；html-output 去重 ✅；Wave 7 [x] rubric 4.9/10；下一次正常干活 |

---

## 5. Mimir 进度笔记

- **main**：`b55fa98` · tier0 **368+2** · **`P0-LONG-CLEARANCE` [x]** · **`P2-LONG-SEM` [x]**
- **身份（2026-05-19）**：Mimir **是智能体**（loop+tools+memory），**不是** DeepSeek 传话桶 — bridge §1
- **Wave 0 A / 1 B / 2 C / D / E**：**[x]**（刘哥 §8.3 签收 2026-05-25）
- **Horizon A**：**[x]** SEM + IQ-EVO Wave 1/2
- **§15 Wave 6**：**[x]** · rubric **4.8/10** documented exception · closeout `p2-long-iqevo-wave6-closeout.md`
- **§15 Wave 7**：**[x]** · rubric **4.9/10** exception · closeout `p2-long-iqevo-wave7-closeout.md`
- **IQ-EVO-48**：**[x]** · main **`a71cc84`** · tier0 **472+2** · Mimir 读 bridge §1「@Mimir 必读」
- **IQ-EVO-47**：**[x]** · `intent_predictor.py` · 待本 commit 后 Gateway 重启
- **粒 A**：`/new` 同步 flush · 同上
- **Gateway**：以 `pgrep gateway/run.py` 为准（部署后重启；勿信本段历史 PID）
- **R5**：刘哥复验 **pass**（30s 内 tool）
- **Gateway**：PID **135797** · /health ok · TRUNCATE since-start **0**
- **GH open**：**10** · #10 **monitoring**（STAB-04 已修）

### MW-D11 勾选表（2026-05-25 · W0-06）

| ID | 状态 | 摘要 |
|----|------|------|
| MW-D01 | [x] | PID **135797** · /health ok |
| MW-D02 | [x] | since-start **0**（全量历史 63 非 P0） |
| MW-D03 | [x] | ERROR 扫：无新 P0 |
| MW-D04 | [x] | 无新 230099 |
| MW-D05 | [x] | session_search hybrid ok |
| MW-D06 | [x] | cross-session 读 runtime home |
| MW-D07 | [x] | `mimir_health_check.sh --quick` **READY**（R3 重试 + restart poll） |
| MW-D08 | [x] | Gateway 十条状态已刷新 |
| MW-D09 | [x] | MAINLINE 与 tier0 一致 |
|| MW-D10 | [x] | GH open **10**；重复 issue 已关 |

---

## 6. Hermes & OpenSpace 对比 — 第二版（2026-05-27 · 新标准）

> **旧版（已废弃，飞书滤镜）**：第一版对比（§6.1～§6.31）使用「飞书不用 X」作为排除理由，已标记为飞书滤镜缺陷。
> 详细数据保留在 `docs/hermes-comparison-detailed.md`，但结论不予采用。
>
> **新标准**：不问「飞书要不要」，问「MimirAether 作为独立智能体需不需要？」
> CLI / Terminal / API / 飞书 / Telegram 都算 Mimir 的能力场景。
>
> **学习三原则**（刘哥 2026-05-27 定）：
> 1. **不复制代码** — 不复制 Hermes/OpenSpace 的具体实现行
> 2. **理解意图** — 理解对方为什么这样设计，解决什么真实问题
> 3. **自己创造** — 用 Mimir 自己的基础设施实现同一意图

### Hermes + OpenSpace 汇总表

| 级别 | Hermes (3项) | OpenSpace (4项) |
|------|-------------|----------------|
| **P0 必须学** | `curator.py`（技能策展）· `subdirectory_hints.py`（语境界限）· `tool_guardrails.py`（工具防护） | `ToolQualityManager`（质量追踪）· `search.py`（混合搜索） |
| **P1 值得学** | `think_scrubber.py`（思考擦除）· `redact.py`（脱敏）· `context_references.py`（引用DSL） | `quality/reviewer.py`（质量审查）· `search_tools.py`（工具搜索） |
| **P2 参考** | 主辅分离·审批概念·终端表现力·插件化搜索 | 三层编排·进化提示分离·进化配置分离·成本估算 |

---

### §6.21 Hermes 三遍思考最终结论（2026-05-27）

**P0 — 必须学（3 项）：**

1. **`curator.py`** — 技能生命周期全自动管理
   - **意图：** 技能会随着使用变得过时、重复、或需要合并。人工管理不可持续，智能体应自动审查自己的技能库
   - **解决什么问题：** Mimir 当前技能增长到 84 个，没有闲置识别、没有自动归档、没有合并建议——全凭手动
   - **Mimir 怎么造：** 已有 `skill_curator.py`（728 行），在基础上加闲置 fork → 子代理审查 → 生命周期自动转换（active/stale/archived），不用 Hermes 代码

2. **`subdirectory_hints.py`** — 工作目录局部上下文感知
   - **意图：** 用户当前在哪个目录工作、这个目录下有什么配置文件（AGENTS.md/CLAUDE.md/README）——智能体应该自动发现，不等用户说
   - **解决什么问题：** Mimir 的 session_search 是全局对话，不知道用户当前工作目录的上下文
   - **Mimir 怎么造：** 270 行轻量实现，从 `MIMIR_REPO_ROOT` 或 `cwd` 向上/下搜索配置文件，注入当前上下文（不是复制 Hermes，用自己路径逻辑）

3. **`tool_guardrails.py`** — 工具调用幂等/重复阻断
   - **意图：** 同一工具在相同的上下文中多次调用=浪费上下文。智能体应在调用前检查是否已经有缓存/正在执行/已失败
   - **解决什么问题：** Mimir 当前工具调用失败后有时自动重试，可能重复 same args
   - **Mimir 怎么造：** 在 `recovery_mixin.py` 基础上加调用缓存（tool_name + args hash → 最近 N 条结果），同一签名重复调用时直接返回缓存，不执行

**P1 — 值得学，低优先级（3 项）：**

4. **`think_scrubber.py`** — 流式思考块擦除稳健化
   - **意图：** DeepSeek 输出可能有 `<think>` 块，流式场景下块可能跨越 chunk。稳健擦除需要逐 chunk 检测完整闭合
   - **解决什么问题：** Mimir 已有基本 think 剥离，但流式场景可能漏掉不完整块
   - **Mimir 怎么造：** 加固现有流式响应处理，加状态机（open_think ← closing_think → closed），不复制 Hermes 实现

5. **`redact.py`** — 运行时输出脱敏
   - **意图：** 工具返回的 API key/token/secret 在显示给用户或送入下一轮 LLM 前自动擦除
   - **解决什么问题：** Mimir 调用 env/tool 时可能泄露敏感信息到上下文
   - **Mimir 怎么造：** 用 `data/` 下规则表（正则列表），在工具结果注入上下文前过 filter，不复制 Hermes 代码

6. **`context_references.py`** — 内联引用 DSL
   - **意图：** 用户在聊自然语言时可以直接引用文件/URL/Git diff，智能体自动展开——比如「看 `@file:src/main.py:20-40`」自动读文件对应行
   - **解决什么问题：** 当前用户需要说「读一下这个文件」，智能体才 read_file。DSL 让引用更自然
   - **Mimir 怎么造：** 自建轻量 DSL 解析器（`@file:` / `@url:` / `@git:`），注入 tool 调用而非系统 prompt，不用 Hermes 语法

**P2 — 模式参考/未来考虑（4 项）：**
7-10. auxiliary_client（主辅分离模式）、approval（审批概念）、display（终端表现力，CLI 通道建后）、web_search_provider（插件化，需第 5 后端时）

**排除：** web_search_provider（插件化，当前 4 后端够用）、display（CLI 通道未建）

---

### §6.22 OpenSpace 三遍思考最终结论（2026-05-27）

**P0 — 必须学（2 项）：**
1. **`ToolQualityManager`**（quality/manager.py + store.py + types.py，~1358 行）
   - **OpenSpace 的意图：** 工具质量是可追踪、可评分、可排序的。不用靠感觉评估
   - **解决什么问题：** 工具描述的完整性、准确性和安全性影响智能体的决策质量。Mimir 当前靠感觉评估「实现代价」
   - **Mimir 怎么造：** 用已有 SQLite 存执行记录，用已有 LLM 能力（非额外付费）做质量评分，用已有 Chroma embedding 做工具-任务相关性排名

2. **`search.py`**（cloud/search.py，~471 行）
   - **OpenSpace 的意图：** 搜索不止一种信号。BM25 精确匹配 + embedding 语义相似度 + lexical boost 加权 = 混合搜索
   - **解决什么问题：** 单一搜索方式在长尾查询中失效。BM25 找不到语义相似的，embedding 找不到精确匹配的
   - **Mimir 怎么造：** Chroma embedding 已有，加 rank_bm25 包（可预装），按四阶段管线重新组织 session_search

**P1 — 值得学，低优先级（2 项）：**

3. **`quality/reviewer.py`**（~566 行）— LLM 自动评估工具描述质量
   - **意图：** 工具描述的质量（完整性、准确性、安全性）不应靠人工审查，应自动化
   - **解决什么问题：** Mimir 当前新增 skill 描述全靠手动检查质量，没有自动审查机制
   - **Mimir 怎么造：** 配套 ToolQualityManager（P0），等 P0 的 quality store 跑通后用 Mimir 自有的 LLM（非额外付费）做自动评估，不复制 OpenSpace 评估逻辑

4. **`search_tools.py`**（~1117 行）— ToolRanker + SearchCoordinator 工具级搜索
   - **意图：** 通用搜索（session_search）搜的是对话历史，工具搜索搜的是工具/技能。两个搜索不应混用
   - **解决什么问题：** Mimir 在执行中需要找到最适合当前任务的工具时，没有专门搜索路径
   - **Mimir 怎么造：** 等 search.py（P0）的混合搜索管线跑通后，复用同一引擎做工具搜索（索引对象换成 skill definitions），不复制 OpenSpace Coordinator 代码

**P2 — 模式参考/未来考虑（6 项）：**
5-10. grounding_agent.py（三层编排，Mimir 架构不匹配）、tool_layer.py（同上）、grounding_client.py（同上）、skill_engine_prompts.py（进化 prompt 分离，先让进化引擎跑起来）、config_evolution.py（进化配置分离，同上）、cost_estimator.py（成本不敏感场景，未来参考）

**排除：** grounding 三层架构（Mimir 单智能体架构不匹配三层编排）、GUI 自动化全套（Mimir 不需要用户交互自动化）

---

### 自检（2026-05-27）

| 问题 | 根因 | 修复 |
|------|------|------|
| 「技能到 100 个再考虑排名」——将需要做的事推延到未来 | 人类式思维：等到瓶颈出现再修。智能体应提前准备 | 修正为「现在就需要排名来辅助技能迭代决策」，已反映在 §6.22 |
| 「实现代价较高」拍脑袋——将 skill_ranker 降为 P2 | 没有查源码验证就凭经验下结论（查后证明改 1 行 key + ~15 行 rank 函数） | 以后评估实现代价必须查源码验证具体改动量，不拍脑袋 |
| 连续两次重复旧回答——看见任务但没理解真正的意图 | 将「回答问题」当成了「完成任务」；忽略了信任问题才是核心 | 根因已写 bridge，但此问题需要刘哥判断我的工作何时恢复到值得信任 |
