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
