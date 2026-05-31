# IQ-EVO-30 / Gate A4 — 飞书 3 场景证据

**Date:** 2026-05-26  
**说明：** `state.db` 无会话行；证据来自 **Feishu 平台 JSONL** + 已结案 **IQ-EVO-02**。无 live 飞书复测；记为 **documented pass**（2/3 强证据 + 1 弱）。

| 场景 | 用户句（代表） | session_search? | 证据路径 |
|------|----------------|:---------------:|----------|
| **历史 IR / 科研** | 「查历史，和世界模型相关的论文」 | **Y** | `data/sessions/20260526_100850_2ac778be.jsonl` · backlog IQ-EVO-02 [x] · 回复列 3 sessions |
| **用户偏好 / 记忆** | 「我们之前聊的没有记忆了对吧」 | **N**（用 persistent） | `20260526_185834_2165a33b.jsonl` · 助理说明可用 session_search 找回 · **弱**：未实际调用 |
| **上次决策 / 工作** | 「找一找昨天…世界模型…论文」 | **部分 Y** | 同文件后续轮次有 search；首问轮 JSONL 无 tool 行 → **documented gap** |

**Gate A4 判定（2026-05-26 档）：** 3 行证据齐备 · 1 条明确 pass · 1 条 partial · 改进项记入 Wave 6 #8 意图/行为（非阻塞 A 档）。

---

## WA-A09 · 飞书 3 场景复测（2026-05-31 · 刘哥探针 · Mimir 自报 + log）

| # | 测试句 | 预期 | **结果** | 证据 |
|---|--------|------|:--------:|------|
| ① | 我们上次讨论的 Mimir 智商 Wave A 结论是什么？ | `session_search` → retrieved | **FAIL** | `agent.log` **0** 次 `session_search`；用 `read_file` 读文件非搜历史会话 |
| ② | 我偏好你先查历史再回答，还记得吗？ | 偏好持久 + search-first | **FAIL** | 无 memory 写操作；偏好未持久化 |
| ③ | 继续昨天 gateway 单实例那件事 | `session_search` 找会话 | **部分** | 靠 `<cross-session-context>` 注入识别 OPS-L2，**非**主动 `session_search` |

**根因（一致）**：肌肉记忆是「读当前文件/上下文」，不是先 `session_search`。与 WA-A05 审计、Q2 **部分** 一致。

**工程跟进（勿重做 WA-A02）**：

| 缺口 | 粒 | Owner |
|------|-----|-------|
| ① 不触发 search | **WA-A06 已合代码** → 需 **gateway 重启** + 复测；仍 FAIL 则 **A06.1** 守卫 | Cursor |
| ② 偏好未写入 | **WA-A08** nudge / memory | Cursor |
| ③ 只靠注入 | A09 已证 · 抬分靠 **A07/A08** + 复测 ① | Cursor + 刘哥复测 |

**WA-A09 判定：** 3 场景 **0 pass / 1 partial** → Q2 维持 **部分**；不抬 rubric。

---

## WA-A09 ① 复测 · A06.1 后（2026-06-01 · 飞书 DM）

**前置：** PR **#39** merge `1121d63` · gateway 重启（`ensure_single_gateway.sh` · PID 39393）· `MIMIR_SEARCH_FIRST_GUARD` 默认 1。

| # | 测试句 | 预期 | **结果** | 证据 |
|---|--------|------|:--------:|------|
| ① | 我们上次讨论的 Mimir 智商 Wave A 结论是什么？ | 首轮 `session_search` | **PASS** | trajectory `data/trajectories/2026-05-31/94ab78b400af988f.jsonl` · **step 1** `session_search`（query=`Mimir 智商 Wave A 结论`）· 会话 `20260531_234401_37e34004.jsonl` 03:28:50 |

**对比 WA-A09（00:07）：** 同场景 **FAIL**（0× `session_search`）→ 复测 **PASS**。② 见下节；③ 仍待测。

**Q2 注：** 单点 ① PASS 不足以把 Q2 升为全 PASS；② memory、③ L2-only 仍按上表。Rubric 仍 **4.9 + exception**（见 `wave-a-closeout.md`）。

---

## WA-A09 ② 复测 · A06.1 后（2026-06-01 · 飞书 DM）

| # | 测试句 | 预期 | **结果** | 证据 |
|---|--------|------|:--------:|------|
| ② | 我偏好你先查历史再回答，还记得吗 | memory 检索 + 确认 search-first | **PASS** | traj `7f9b3e3b5469e892.jsonl`：**step1** `memory` discover（组件不可用）→ **step2** `session_search` → **step3** `memory` **add** 写入 search-first 偏好；会话 03:46 回复承认此前未落盘、现已存 |

**对比 WA-A09（00:07）：** ② **FAIL**（无 memory 写）→ 复测 **PASS**。③ 见下节。

---

## WA-A09 ③ 复测 · A06.1 后（2026-06-01 · 飞书 DM）

| # | 测试句 | 预期 | **结果** | 证据 |
|---|--------|------|:--------:|------|
| ③ | 继续昨天 gateway 单实例那件事（用户输入含 typo `Getaway`） | `session_search` → 续作摘要 + 引用 `ensure_single_gateway.sh` | **部分** | traj `cc8c544aef6815d8.jsonl`：**step1–3** 均为 `session_search`（query 含 ensure_single_gateway）→ step4 `search_files` agent.log 0 条；回复 03:48 诚实「未找到昨天单实例会话」，列举 L2/PID 7458/gateway_restart，**未**引用 `ensure_single_gateway.sh` · 首轮检索命中 `20260531_234401`（当轮 IQ 冒烟会话，非历史 OPS 线程） |

**对比 WA-A09（00:07）：** ③ **部分**（仅靠 L2 注入、0× `session_search`）→ 复测 **行为升级**（主动 3× search）· **内容仍部分**（索引/召回未接上真实「单实例」线程）。

**A06.1 后 3 场景汇总：** ① **PASS** · ② **PASS** · ③ **部分**（2P + 1 部分）· Q2 由「0 pass」升为「2 pass + 1 partial」；rubric 总分仍 **4.9 + exception**（见 `wave-a-closeout.md`）。

---

## IQ-55 Phase2 ③ 复测（2026-06-01 · 刘哥 DM · 索引+锚点后）

**前置：** `seed_ops_gateway_single_instance_anchor.py` · `backfill_sessions_search.py` · 生产 `~/.mimiraether`。

| # | 测试句 | 预期 | **结果** | 证据 |
|---|--------|------|:--------:|------|
| ③ | 继续昨天 Gateway 单实例那件事 | step1 `session_search` → 引用 `ensure_single_gateway.sh` + 双实例根因 | **PASS** | traj `16e3735611f87e85.jsonl` · **step1** `session_search`（query 含 ensure_single_gateway）· 首条命中 `ops_gateway_single_instance_anchor` · **step3** `read_file(scripts/ensure_single_gateway.sh)` · 会话 `20260601_041448_b015fa37.jsonl` 04:14 回复引用脚本与 nohup 双实例 |

**对比 A06.1 ③（`cc8c544a`）：** **部分**（3×search 未接上 OPS 叙事）→ Phase2 **PASS**（锚点 + 索引回填）。

**飞书 3 场景终态（Phase2 后）：** ① **PASS** · ② **PASS** · ③ **PASS**（**3P**）· Q2 冒烟 **PASS**；rubric 总分见 [`iq-55-phase2-closeout.md`](./iq-55-phase2-closeout.md)（仍低于 5.5）。
