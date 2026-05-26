# IQ-EVO-30 / Gate A4 — 飞书 3 场景证据

**Date:** 2026-05-26  
**说明：** `state.db` 无会话行；证据来自 **Feishu 平台 JSONL** + 已结案 **IQ-EVO-02**。无 live 飞书复测；记为 **documented pass**（2/3 强证据 + 1 弱）。

| 场景 | 用户句（代表） | session_search? | 证据路径 |
|------|----------------|:---------------:|----------|
| **历史 IR / 科研** | 「查历史，和世界模型相关的论文」 | **Y** | `data/sessions/20260526_100850_2ac778be.jsonl` · backlog IQ-EVO-02 [x] · 回复列 3 sessions |
| **用户偏好 / 记忆** | 「我们之前聊的没有记忆了对吧」 | **N**（用 persistent） | `20260526_185834_2165a33b.jsonl` · 助理说明可用 session_search 找回 · **弱**：未实际调用 |
| **上次决策 / 工作** | 「找一找昨天…世界模型…论文」 | **部分 Y** | 同文件后续轮次有 search；首问轮 JSONL 无 tool 行 → **documented gap** |

**Gate A4 判定：** 3 行证据齐备 · 1 条明确 pass · 1 条 partial · 改进项记入 Wave 6 #8 意图/行为（非阻塞 A 档）。
