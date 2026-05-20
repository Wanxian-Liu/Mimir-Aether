# Mimir d1–d7 能力审计与训练任务包

> **用途**：刘哥不在电脑旁时，由 **Cursor 工程** 产出本文件 → **Mimir** 按任务自我验证、迭代、记 ISSUES/文档（**不改** `agent/`/`gateway/`/`mimir_cli/` 架构）。  
> **真源队列**：`docs/MIMIR_EXEC_BACKLOG.md` §2（工程 E-* 与 M-* 仍在那里排期）。  
> **Wiki 审计原文**（只读、**勿改 HTML**）：`~/.openclaw/wiki/main/iterations/d{1..7}-audit-report.html`  
> **评注与经验（必读）**：`docs/MIMIR_D17_WIKI_AUDIT_COMMENTARY.md` — 对照真源逐阶段评价与建议  
> **本包版本**：2026-05-20 **post E-002/E-003 commit**（Mimir 跑 **T-01～T-11** + 可选读评注练审计思维）

---

## 0. 习惯约定（持续）

| 谁 | 何时 | 做什么 |
|----|------|--------|
| **Cursor** | 刘哥离线 / 工程窗收尾 | 更新本文件「审计分 + 任务表」；给每条任务：**方案 + 验证命令 + 整段提示词** |
| **Mimir** | 收到本文件或 §9 指向 | 按 **T-*** 顺序执行 → 自证 → 更新 `MIMIR_ISSUES.md` / `GATEWAY_STABILITY_BACKLOG.md` / backlog 状态 |
| **刘哥** | 回归 | 飞书复验、OPENROUTER、授权 push（M-008） |

**Mimir 禁止**：改架构；删光 `role=tool`；填 d5 十九个进化存根；commit `data/persistent.json`；未授权 `git push`。

---

## 1. d1–d7 再审计（Mimir 能做什么）

评分沿用 wiki **综合分**；「Mimir 能力 2026-05-20」= 历史表现 + 续跑窗证据。

| 阶段 | 范围 | Wiki 分 | Mimir 已证明 | 仍薄弱 | 本轮训练（T-*） |
|------|------|---------|--------------|--------|-----------------|
| **d1** | 飞书适配器 | ~6/10 | 通道连通、发消息成功、收图 `Image downloaded`（P2） | 识图需 OPENROUTER；卡片 #9 待复验 | **T-02** **T-03** **T-05** |
| **d2** | 上下文/压缩 | ~6/10 | 孤儿 tool grep；压缩链存在（cd6b71d） | 不会改压缩算法；长会话截断仅观察 | **T-04**（只读观察） |
| **d3** | Gateway 框架 | ~5–6/10 | 硬重启 + pgrep；十条文档；**E-001/E-002 已 commit** | Watchdog/#4 需工程 | **T-01**（commit 后回归）**T-06** **T-07** |
| **d4** | Agent 核心循环 | 6/10 | M4 tool 触发；无 `tool must` | #10 崩溃需收栈 | **T-04** **T-08** |
| **d5** | 自修/进化 | 4.5/10 | 只读 ADR/evolution_log | 不能写进化 SKILL | **T-09**（只读 + 一条观察） |
| **d6** | 可观测性 | 5.5/10 | grep 日志 | 不接 SQL/monitor 代码 | **T-10**（日志基线） |
| **d7** | CLI 双轨 | 4/10 | `cli.py version` 等（mimir_prod_smoke） | `CLI_CONFIG` 未修 | **T-11**（复现记 ISSUES） |

**综合结论**：Mimir 适合 **冒烟、复现、证据链、文档状态**；d5–d7 **代码债** 留给 Cursor（E-004～E-009）。训练目标是：**每条任务都能「命令 → 证据 → 文档」闭环**，为日后自我迭代打样。

---

## 2. 任务总表（按顺序执行）

| ID | 对应 backlog | 标题 | 成功标准（自证） |
|----|--------------|------|------------------|
| **T-01** | M1 | Gateway 硬重启复验（**commit 后 main**） | `pgrep` 有 PID；日志含 Lark wss；启动段无 `Gateway stopped` |
| **T-02** | M-002 | 飞书发图 + 下载链 | `grep 'Image downloaded'` 有命中 |
| **T-03** | M-003 | 空表头表卡片 | 飞书见列名 `—`；日志无 `230099` |
| **T-04** | d2/d4 | 工具对话 + 孤儿 tool 复验 | 触发 tool 后 `grep -c 'tool must'` = 0 |
| **T-05** | M-005 + d1 | OPENROUTER 存在性（不泄露） | 回报「有/无」+ 是否尝试识图 |
| **T-06** | 十条 #5 | API Server 安全清单 | 表格填完：bind、key、loopback 结论 |
| **T-07** | 十条 #3 | Reaction 未处理 | 复现或记「未复现 + 条件」→ ISSUES |
| **T-08** | 十条 #10 | Agent 崩溃栈采集 | `agent.log` 崩溃段摘要或「近期无崩溃」 |
| **T-09** | d5 | 进化只读观察 | 读 `evolution_log` 末 5 行 + ISSUES 一条观察 |
| **T-10** | d6 | 可观测 Day-0（日志） | 统计 24h 内 ERROR 条数 +  top 3 模式 |
| **T-11** | d7 | CLI_CONFIG 复现 | 复现 ImportError 路径写入 ISSUES |
| **T-12** | 知识 | **Wiki 评注核对**（可选） | 任选 d1–d7 各 1 条 P0 → `grep`/日志验证 → 与 `MIMIR_D17_WIKI_AUDIT_COMMENTARY.md` 对照 |

完成每条后：更新 `docs/GATEWAY_STABILITY_BACKLOG.md` 对应行（若适用）+ `docs/MIMIR_EXEC_BACKLOG.md` §4 状态 + 回报 §6 模板。  
**T-12**：在回报加「wiki 仍真 / 已过时」各至少 1 条（见评注文档末「审计思维」）。

---

## 3. 任务明细（方案 + 验证 + 提示词）

### T-01 — Gateway 硬重启复验

**方案**  
1. 在仓库根执行硬重启脚本（使用 `MIMIR_AETHER_HOME`）。  
2. `pgrep` 确认 `gateway/run.py` 常驻 ≥60s。  
3. `tail` gateway.log：应有 `feishu connected` / `Lark connected`；**不应**在启动后 30s 内出现 `Gateway stopped`。

**验证命令**

```bash
cd ~/src/MimirAether
export MIMIR_AETHER_HOME=~/.mimiraether
./scripts/restart_gateway_hard.sh
sleep 5
pgrep -af 'gateway/run.py'
grep -E 'feishu connected|Lark connected|Gateway stopped|Unclosed' "$MIMIR_AETHER_HOME/logs/gateway.log" | tail -20
```

**Mimir 提示词（整段复制）**

```markdown
执行 docs/MIMIR_D17_AUDIT_AND_TASKS.md 的 T-01。
- 只跑命令与 grep，不改代码。
- 回报：PID、启动时间线索、日志最后 20 行相关行摘要。
- 通过标准：有 pgrep；有 Lark wss；启动段无 Gateway stopped。
- 通过后把 docs/MIMIR_EXEC_BACKLOG.md §4 的 M1 标为 [x]。
```

---

### T-02 — 飞书发图 + 下载链

**方案**  
1. 在飞书对 **mimiraether** 机器人发一张图（或让刘哥代发）。  
2. 查 `agent.log`：`Image downloaded` / 下载路径。  
3. 若已有 `OPENROUTER_API_KEY`（T-05），再问「描述这张图」；若无则标 **blocked: M-005**。

**验证命令**

```bash
grep -E 'Image downloaded|download.*image|vision|OPENROUTER' ~/.mimiraether/logs/agent.log | tail -15
```

**Mimir 提示词**

```markdown
执行 T-02（docs/MIMIR_D17_AUDIT_AND_TASKS.md）。
- 需要飞书发图；若无法发图，写阻塞原因。
- grep agent.log，勿打印 API key。
- 回报：发图时间、grep 命中、识图是否 blocked。
- 更新 MIMIR_EXEC_BACKLOG M-002 为 [x] 或 [~]。
```

---

### T-03 — 空表头表（#9）

**方案**  
向机器人发送含空 `<th></th>` 的 HTML 表格（或刘哥代发）。期望列名显示为 `—`，且无错误码 `230099`。

**样例消息（可改编）**

```html
<table><tr><th></th><th>列B</th></tr><tr><td>a</td><td>b</td></tr></table>
```

**验证**

```bash
grep -E '230099|normalize_table|feishu.*card' ~/.mimiraether/logs/gateway.log ~/.mimiraether/logs/agent.log 2>/dev/null | tail -10
```

**Mimir 提示词**

```markdown
执行 T-03。飞书端到端确认表头为 —；grep 日志无 230099。
更新 GATEWAY_STABILITY_BACKLOG #9 与 MIMIR_EXEC_BACKLOG M-003。
```

---

### T-04 — 工具对话 + 孤儿 tool

**方案**  
在飞书或 CLI 触发一次会调用 **terminal** 或 **read_file** 的请求（与 mimir_prod_smoke A3 一致）。完成后：

```bash
grep -c 'tool must be a response' ~/.mimiraether/logs/agent.log || true
grep -E 'tool_call|terminal|read_file' ~/.mimiraether/logs/agent.log | tail -10
```

**通过**：`tool must` 计数为 0。

**Mimir 提示词**

```markdown
执行 T-04。触发至少一次 tool；证明无 orphan tool 错误。
勿改 messages 过滤逻辑。回报工具名与 grep 结果。
```

---

### T-05 — OPENROUTER 存在性

**方案**

```bash
grep -q '^OPENROUTER_API_KEY=' ~/.mimiraether/.env 2>/dev/null && echo OPENROUTER:present || echo OPENROUTER:absent
# 禁止 cat 整份 .env 到聊天
```

有 key 则再做 T-02 识图一步；无 key 则 ISSUES 记「M-005 阻塞 M-002 识图」。

**Mimir 提示词**

```markdown
执行 T-05。只回报 present/absent，不贴密钥。更新 M-005 状态。
```

---

### T-06 — API Server 安全清单（十条 #5）

**方案**  
读 `docs/SECURITY.md` §2 与 `gateway/platforms/api_server.py` 中 bind/key 逻辑，填表：

| 检查项 | 你的实测/代码结论 |
|--------|-------------------|
| 监听地址 | 127.0.0.1 / 0.0.0.0 / 其它 |
| 非 loopback 是否强制 key | 是/否 |
| 当前 `config.yaml` api_server 段 | 有/无 + 端口（无密钥值） |
| 是否符合 SECURITY 说明 | 是/否/需刘哥 |

**Mimir 提示词**

```markdown
执行 T-06。只读 SECURITY + api_server.py + ~/.mimiraether/config.yaml（勿贴 key）。
把表格写入 MIMIR_ISSUES 新条目或追加 GATEWAY_STABILITY_BACKLOG #5 状态为「已验证」。
```

---

### T-07 — Reaction 未处理（十条 #3）

**方案**  
在飞书对一条机器人消息点表情 reaction；观察 gateway.log 是否处理或报错。

```bash
grep -i reaction ~/.mimiraether/logs/gateway.log | tail -15
```

无日志则记 ISSUES：`#3 reaction — 未复现，条件：…`。

**Mimir 提示词**

```markdown
执行 T-07。复现或明确未复现条件；更新十条 #3。
```

---

### T-08 — Agent 崩溃栈（十条 #10）

**方案**

```bash
grep -E 'Traceback|CRITICAL|Agent.*crash|Fatal' ~/.mimiraether/logs/agent.log | tail -30
```

有栈：摘 **前后各 25 行** 写入 ISSUES #10 草稿（无密钥）。无：状态改为「近期无崩溃（日期）」。

**Mimir 提示词**

```markdown
执行 T-08。只收集日志，不修 core_loop。
```

---

### T-09 — 进化只读（d5）

**方案**  
1. `tail -5 docs/evolution_log.md`  
2. `ls skills/mimiraether/mimiraether-self_evolution/`（只看结构）  
3. 在 `MIMIR_ISSUES.md` 追加 **一条** 观察（≤5 行）：例如「进化 skill 存在但自动 FIX 未 e2e 验证」——**不要**实现 D5-2。

**Mimir 提示词**

```markdown
执行 T-09。d5 只读。禁止改 evolve 代码或填 19 存根。
```

---

### T-10 — 可观测 Day-0（d6，仅日志）

**方案**

```bash
LOG=~/.mimiraether/logs/errors.log
[ -f "$LOG" ] || LOG=~/.mimiraether/logs/agent.log
grep -i error "$LOG" 2>/dev/null | tail -50 | cut -c1-120 | sort | uniq -c | sort -rn | head -5
```

回报：ERROR 大致条数 + top 3 模式（脱敏）。

**Mimir 提示词**

```markdown
执行 T-10。不装 monitor、不改 insights SQL。为日后 D6 工程留基线数字。
```

---

### T-11 — CLI_CONFIG 复现（d7）

**方案**

```bash
cd ~/src/MimirAether
python3 -c "from mimir_cli.config import CLI_CONFIG; print('ok', list(CLI_CONFIG.keys())[:5])" 2>&1
python3 cli.py chat --help 2>&1 | head -5
```

预期：可能 `ImportError: CLI_CONFIG`。将 **完整 traceback 首行 + 文件路径** 写入 `MIMIR_ISSUES.md`（供 Cursor E-004）。

**Mimir 提示词**

```markdown
执行 T-11。只复现与记录，不修 mimir_cli。
```

---

## 4. 自我验证与迭代循环（每条任务）

```text
执行 → 对照「成功标准」→ 失败则第二轮（换条件/补 grep）→ 仍失败记 ISSUES 停手
     → 通过则更新文档状态 → 可选：在回报里写「下一轮建议」一条
```

**进化（轻量）**：全部 T-* 完成后，在回报末尾加一节 **「Mimir 自评」**（各 1 句）：

- d1–d3：端到端信心 1–5  
- 最大阻塞项（是否总是 M-005）  
- 希望 Cursor 下一刀工程项（E-002 / E-004 / …）

---

## 5. 给 Mimir 的总提示词（新窗一键）

```markdown
# Mimir 训练窗 — d1–d7 任务包

工作区：~/src/MimirAether  
运行时：MIMIR_AETHER_HOME=~/.mimiraether  
必读：docs/MIMIR_D17_AUDIT_AND_TASKS.md + docs/MIMIR_D17_WIKI_AUDIT_COMMENTARY.md（评注，勿改 wiki HTML）  
队列：docs/MIMIR_EXEC_BACKLOG.md §2

你是 **Mimir**：冒烟、证据、文档、ISSUES。禁止改 agent/gateway/mimir_cli 架构；禁止提交 persistent.json；禁止 push。

## 已知基线（2026-05-20 post-commit，勿重做工程）
- E-001/E-002/E-003 已在 **main 工作区 commit**（gateway 6 mixin + agent 4 mixin + `@property` 修复）
- 你的任务：**只冒烟与文档**，不要改 mixin 架构、不要 push
- M-007 十条状态列已有；T-06/07/08 可细化

## 今日顺序
按 docs/MIMIR_D17_AUDIT_AND_TASKS.md §2 执行 T-01 → T-11，每条用 §3 的验证命令自证。

## 回报格式（全部完成后一次发）
### 分项
| 任务 | 结果 | 证据一行 |
| T-01 | pass/fail/blocked | … |
… T-11 …

### Mimir 自评（§4）
…

### 需刘哥
- OPENROUTER / 飞书代发 / push 授权

### 建议 Cursor 下一刀
E-002 commit / E-004 / …
```

---

## 6. 回报模板（粘贴用）

```text
Mimir d1–d7 训练回报 — 2026-__-__
基线: gateway PID ___ ; tier0 未跑/已跑

| 任务 | 结果 | 证据 |
|------|------|------|
| T-01 | | |
| T-02 | | |
| T-03 | | |
| T-04 | | |
| T-05 | | |
| T-06 | | |
| T-07 | | |
| T-08 | | |
| T-09 | | |
| T-10 | | |
| T-11 | | |

自评: d1-d3 信心 _/5 ; 最大阻塞: ___ ; 建议工程: ___

已更新文档: [ ] GATEWAY_STABILITY  [ ] MIMIR_EXEC §4  [ ] MIMIR_ISSUES
```

---

## 7. Cursor 工程窗（刘哥在时）— 与 Mimir 并行

| 项 | 状态 | 说明 |
|----|------|------|
| E-001 | [x] | `@property` 常驻 |
| E-002/003 | [x] | 2026-05-20 commit；tier0 162+2 |
| **下一刀工程** | [ ] | **E-004** `CLI_CONFIG`（可用 Mimir T-11 的 ISSUES 作输入） |
| M-008 | [ ] | push 需刘哥授权 |

**Mimir 窗勿**改 E-004 代码；复现交给 T-11 即可。
