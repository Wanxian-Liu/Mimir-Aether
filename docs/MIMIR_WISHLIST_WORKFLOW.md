# Mimir 心愿单工作流（MW · 可执行真源）

> **读者**：Mimir（主执行）· 刘哥（拍板/本机 shell）· Cursor（复核/大改）  
> **立案**：2026-06-02 · 来源：Mimir 飞书「最想做的 6 件事」+ 刘哥：**无 🔴 风险项均同意**  
> **队列表**：[`MIMIR_TASK_QUEUE.md`](./MIMIR_TASK_QUEUE.md) **§13**  
> **下一粒**：`./scripts/mimir_wish_run_next.sh --dry-run`

---

## 0. 真相对齐（必读，避免重复劳动）

| Mimir 诉求 | 仓库现状（2026-06-02 `main`） | §13 怎么处理 |
|------------|-------------------------------|--------------|
| **P0 合入 IQ-31/32/33/34** | **已合** `a0dc323`（`agent_loop` WM 注入、`intent_predictor` fallback、`test_iq33_*`） | **MW-00** 只做验收 + 更新 backlog，**禁止**再写一遍 +105 行 |
| **P0 search_first_guard 接线** | **已接** `agent_loop.py`（import + turn 末 `should_block_text_only_finish`）；`core_loop` 委托 `MimirAgentLoop` | **MW-01** 审计 closeout；仅当审计发现第二条执行路径缺失时才补线 |
| **P1 并行工具 IQ-41** | 仅设计稿 | **MW-02** 实现（env 默认关） |
| **P1 去飞书化** | 设计稿暗含 | **MW-03** 薄抽象层（不绑 Feishu session） |
| **P2 nudge 间隔 IQ-40** | 已有 `conversation_nudges.py`（memory/skill 分轨间隔） | **MW-04** 统一 `MIMIR_NUDGE_INTERVAL` 周期检查 |
| **P2 ISSUES #4** | **ISSUES #4 已关**（persistent 截断 · ADR-001）；真实痛点是 **IC 顾问空建议**（`ic_advisor` 同目录无替代） | **MW-05** 修 `ic_advisor` 搜索范围 + 测 |

**生产数据**：WM 要出数需刘哥 shell：`MIMIR_WM_PREDICTOR=1` + gateway 重启（**Owner=刘哥**，Mimir 写 `docs/phase0/mw-00-prod-env.md` 即可）。

---

## 1. 何时跑本链

```text
./scripts/mimir_iq17_run_next.sh --dry-run   → 若可执行 IQ 粒，先 §11
./scripts/mimir_eng_run_next.sh --dry-run    → 若可执行 ENG-WF 粒，先 §12
./scripts/mimir_wish_run_next.sh --dry-run   → 否则跑 §13（本文）
```

| 顺序 | 链 |
|:----:|-----|
| 1 | §11 IQ-17（仅剩 IQ-12 BLOCK 时跳过） |
| 2 | §12 ENG-WF（已全 [x] 则跳过） |
| 3 | **§13 MW（本文）** |
| 4 | §10 SELF-LOOP / §6.1 周常 |

---

## 2. 每轮开场（复制给 Mimir）

```text
你是 Mimir 心愿单轨（MW）。刘哥已拍板：§13 中无 🔴 项均可做；env 默认关；每粒 commit+push。

1) ~/.openclaw/workspace/CLAUDE.md
2) ~/src/MimirAether/AGENTS.md
3) 本文 §3 单粒循环
4) TASK_QUEUE §13 第一条 [ ]（./scripts/mimir_wish_run_next.sh --dry-run）
5) MIMIR_IQ_EVOLUTION_DIRECTION §3.3 回报

纪律：只改 §4 列出的路径；禁止 commit data/persistent.json；
禁止飞书内 restart gateway；改 agent|tests → tier0 + record_m6；
做完立刻下一粒，禁止问「继续吗」。
```

---

## 3. 单粒循环

```text
【MW 单粒 — <ID>】
0) ./scripts/mimir_wish_run_next.sh --dry-run
1) git pull --rebase origin main
2) Read 本文 §4 <ID>
3) 实现 / 审计（Surgical）
4) 跑 §4「验证」全部命令，摘要写入 phase0 closeout
5) 若改 agent|gateway|tools|tests：
     ./run_ralph_tier0.sh && ./scripts/record_m6_evolution.sh "MW-xx: …"
6) git commit + push origin main
7) TASK_QUEUE §13 [x]；bridge §4 一行
8) ./scripts/mimir_wish_run_next.sh --dry-run → 下一 ID
```

---

## 4. 任务粒定义

### MW-00 — P0-A：验收 IQ-31/32/33/34（已合 main）

**做什么**

- `git pull` 后确认 `a0dc323` 在 `git log main` 中。
- 跑：`pytest tests/agent/test_iq33_non_redundant_nudges.py tests/agent/test_intent_predictor.py -q`
- `grep -n wm_predict agent/agent_loop.py` 有注入块。
- 更新 [`docs/proposals/iq17-cursor-backlog.md`](./proposals/iq17-cursor-backlog.md)：**P0 表改「已合 a0dc323」**，勿再开实现 PR。
- 写 [`docs/phase0/mw-00-iq31-34-verify.md`](./phase0/mw-00-iq31-34-verify.md)（命令输出摘要）。
- 写 [`docs/phase0/mw-00-prod-env.md`](./phase0/mw-00-prod-env.md)：`MIMIR_WM_PREDICTOR=1` 步骤（**刘哥执行**）。

**禁止**：重复修改 `agent_loop.py` / `intent_predictor.py` 除非 tier0 红且为修回归。

**验证**

```bash
git merge-base --is-ancestor a0dc323 HEAD && echo OK
pytest tests/agent/test_iq33_non_redundant_nudges.py tests/agent/test_intent_predictor.py -q
```

**建议 commit**：`docs(phase0): MW-00 verify IQ-31~34 merged on main`

---

### MW-01 — P0-B：search_first_guard 接线审计

**做什么**

- 全仓库：`rg 'search_first_guard|should_block_text_only_finish' agent/` → 记录命中文件。
- 确认生产路径：`core_loop` → `MimirAgentLoop.run`（见 `core_loop.py` ~825+）。
- 写 [`docs/phase0/mw-01-search-first-wiring-audit.md`](./phase0/mw-01-search-first-wiring-audit.md)：
  - 结论：**已接线** 或 **缺口的具体文件+行号**。
- **仅当** 发现 `MimirAgentLoop` 之外仍有「无工具纯文本结束」路径且未调用 guard → 最小补线 + 1 测。

**禁止**：重写 `search_first_guard.py`；改 gateway 飞书适配层。

**验证**

```bash
rg -l search_first_guard agent/
pytest tests/agent/test_search_first_guard.py tests/agent/test_nudge_contract.py -q
./run_ralph_tier0.sh   # 仅当改了 .py
```

**建议 commit**：`docs(phase0): MW-01 search-first wiring audit`（或 `fix(agent): …` 若补线）

---

### MW-02 — P1-A：并行工具（IQ-41 实现）

**真源**：[`docs/proposals/iq17-parallel-tools-design.md`](./proposals/iq17-parallel-tools-design.md)

**做什么**

1. 新建 `agent/parallel_dispatcher.py`：只读工具并行、`asyncio.gather` 或现有 executor；写操作串行。
2. `agent_loop.py`：在 `for tc in tool_calls` 处接入；`MIMIR_PARALLEL_TOOLS=0` 默认关。
3. 新增 `tests/agent/test_parallel_dispatcher.py`（≥4：全只读并行、含 write 串行、env off、单工具退化）。

**禁止**：默认开并行；并行 `write_file`/`memory`/`terminal`；改飞书 adapter。

**验证**

```bash
pytest tests/agent/test_parallel_dispatcher.py -q
MIMIR_PARALLEL_TOOLS=0 pytest tests/agent/test_parallel_dispatcher.py -q
./run_ralph_tier0.sh
```

**建议 commit**：`feat(agent): parallel read-only tool dispatch (MIMIR_PARALLEL_TOOLS, default off)`

---

### MW-03 — P1-B：工具调度与平台解耦（薄层）

**做什么**

- 新建 `agent/tool_dispatch_context.py`（或同名模块）：
  - `ToolDispatchContext`：`session_id`, `channel`（`cli|feishu|api`）, `workspace_root` — **无** lark/openclaw 类型。
- `agent_loop` / `parallel_dispatcher` 只依赖该 dataclass，不 import gateway。
- 写 [`docs/phase0/mw-03-platform-agnostic-dispatch.md`](./phase0/mw-03-platform-agnostic-dispatch.md) 一页（与 IQ-41 如何配合）。

**禁止**：大改 gateway；重命名全仓库 session 模型。

**验证**

```bash
pytest tests/agent/test_parallel_dispatcher.py tests/agent/test_tool_dispatch_context.py -q  # 若有新测
python3 -c "from agent.tool_dispatch_context import ToolDispatchContext; ToolDispatchContext('s','cli','/tmp')"
./run_ralph_tier0.sh
```

**建议 commit**：`feat(agent): platform-agnostic tool dispatch context (MW-03)`

**依赖**：建议在 **MW-02 之后**（队列已按序）。

---

### MW-04 — P2-A：对话内周期 nudge（IQ-40）

**真源**：[`docs/proposals/iq17-conversation-nudge-design.md`](./proposals/iq17-conversation-nudge-design.md)

**做什么**

- `agent_loop.py`：`turn > 0` 且 `turn % N == 0`（`MIMIR_NUDGE_INTERVAL`，默认 **3**，`0`=关）时：
  - 复用 `maybe_memory_nudge_message` / `maybe_skill_nudge_message` / 可选 skill_route（勿与 turn0 抢占）。
- 新增 `tests/agent/test_conversation_nudge_interval.py`（≥3）。

**禁止**：异步侧信道；turn0 触发；默认 N=1。

**验证**

```bash
pytest tests/agent/test_conversation_nudge_interval.py -q
./run_ralph_tier0.sh
```

**建议 commit**：`feat(agent): MIMIR_NUDGE_INTERVAL periodic nudges (default 3, off=0)`

---

### MW-05 — P2-B：IC 顾问空建议修复（非 ISSUES #4）

**做什么**

- 改 `agent/self_evolution/engine.py` `ic_advisor()`：
  - 同目录无替代时，扩大到 `agent/prompts/`、同 tier 低 `blast_radius` 文件（见 `state_encoder` 图）。
  - `suggestion` 永不为空模板句：至少给「改 tests/ 或 开 HANDOFF」类通用建议。
- 新增 `tests/agent/test_ic_advisor_alternatives.py`（拦截 `agent_loop.py` 时 alternatives≥1 或 suggestion 非空）。

**禁止**：放开 PROTECTED_FILES 硬拦截；改 ADR-001 双写策略。

**验证**

```bash
pytest tests/agent/test_ic_advisor_alternatives.py -q
./run_ralph_tier0.sh
```

**建议 commit**：`fix(agent): ic_advisor wider fallback when protected file blocked`

---

### MW-90 — 收官

**做什么**：`docs/phase0/mw-wishlist-closeout.md` — 六诉求对照表、tier0 终值、刘哥待办（WM env / gateway）。

**验证**：`./run_ralph_tier0.sh`

---

## 5. bridge §4 模板

```text
| <date> | **<MW-xx>** | **Mimir** | <一句：做了什么> · tier0 N/M · commit <hash> |
```

---

## 6. 修订日志

| 日期 | 摘要 |
|------|------|
| 2026-06-02 | 初版：刘哥拍板 §13；P0 真相对齐；MW-00～05 + MW-90 |
