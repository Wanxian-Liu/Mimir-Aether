# 飞书体验升级 — 实现设计草稿（Mimir 自做 · 2026-09-27）

任务单：`~/wiki/discussions/2026-09-27-飞书体验升级-已读表情与播报.md`（status: mimir）
目标：A 已读表情（inbound 前置 hook · 零 LLM · 1 秒回执 👀）· B 工作状态播报（开工🔧/中途⚙️×2/完工✅ · 防刷屏）

## 0. 盘上取证（本轮已验证的事实）

| 事实 | 证据 |
|---|---|
| feishu_adapter.py = 1355 行，零 reaction | grep 'reaction' 该文件 → 0 命中 |
| 入站链路 | `_sync_p2_im_message_receive_v1`(869) → run_coroutine_threadsafe(886) → `_async_dispatch_p2`(897) → `handle_message(event)`(924) |
| 入站前置点已存在 | `_async_dispatch_p2` 顶部：image 预下载 → typing → handle_message |
| send 能力现成 | `FeishuAdapter.send(chat_id, content, reply_to=..., metadata=...)`(1034)，aiohttp 直发；`_headers()`(609) 带 tenant token |
| 生命周期钩子现成且 Feishu 未覆写 | base.py:1395 `on_processing_start` / 1398 `on_processing_complete(event,outcome)`；调用点 1665 / 1846-1876；`ProcessingOutcome`(649) |
| 中途步骤信息现成 | agent_mixin.py:889 `_step_callback_sync(iteration, prev_tools)`（已 emit agent:step） |
| Feishu 无工具进度根因 | agent_mixin:770 `if type(adapter).edit_message is _BaseAdapter.edit_message: return` — Feishu 未实现 edit_message ⇒ 进度被整队丢弃 |
| 已有 read receipts 但非 reaction | feishu_adapter:780 `_lark_noop_message_read_v1` 只发文本「刘哥读了你的消息」（300s 节流） |

## 1. 方案（三处改动，零新服务、零 LLM）

1. **新模块 `gateway/work_status.py`** — `WorkStatusBroadcaster`：纯逻辑（摘要清洗/封顶/节流/去重），异步 `_emit` 走传入的 adapter.send。额度：每 run ≤4 条（1 开工 + ≤2 中途 + 1 完工），最小间隔 2.0s，同一文本不重发。
2. **`gateway/platforms/feishu_adapter.py`** —
   - `_add_reaction(message_id, emoji_type)` / `_delete_reaction(message_id, reaction_id)`（aiohttp + tenant token + 401/99991663 刷新后重试一次 + 全异常兜底）
   - `_react_inbound(message_id)` 在 `_async_dispatch_p2` **顶部** fire-and-forget（不阻塞入站）⇒ 👀 毫秒级
   - 覆写 `on_processing_start` → 🔧 开工播报；`on_processing_complete(outcome)` → 删 👀 / 加 ✅ + ✅ 完工播报
   - `send()` 内 `record_reply()` 供「完工：结果一句」取材（不含状态类前缀的消息）
3. **`gateway/agent_mixin.py`** — `_step_callback_sync` 内追加 `run_coroutine_threadsafe(broadcaster.step(...))`（自包含 try/except，失败不影响主流程）⇒ ⚙️ 中途 ≤2 条。

## 2. 验收读数对照（任务单四条）

1. `grep -c reaction gateway/platforms/feishu_adapter.py` ≥ 3
2. 实测：刘哥发消息后 1 秒内见 👀（刘哥亲眼=终验）
3. 三段播报各至少一次实测（开工/中途/完工）
4. 防刷屏自证：连续任务中播报条数 ≤ 4

## 3. 待办

- [ ] 权限预验：`POST /open-apis/im/v1/messages/{message_id}/reactions` 是否可用（emoji_type 实测 EYES/DONE）
- [ ] 落码 + 单测（封顶/节流/去重）
- [ ] 重启 Gateway 生效 + 真机实测

## 4. 实测发现与落地结果（2026-09-27 更新）

| 项 | 实测结论 |
|---|---|
| emoji_type 「EYES」 | **不存在** —— API 返回 `HTTP 400 code=231001 reaction type is invalid`（任务单提示的 EYES 是错的） |
| 有效值来源 | 官方表情列表文档（135 项：OK/THUMBSUP/THANKS/DONE/SMILE/GLANCE/…） |
| 已读回执取值 | 改用 **GLANCE**（唯一「看/瞄」类）；可用 `MIMIR_FEISHU_REACTION_READ` 覆盖 |
| 完工取值 | **DONE**（可用 `MIMIR_FEISHU_REACTION_DONE` 覆盖） |
| 权限面 | GLANCE/DONE/OK/THUMBSUP/SALUTE/SMART/THINKING 全部 `code=0` —— 权限够，无需改应用配置 |
| 延迟 | 加表情 256~297 ms（隔离实测）——远低于「1 秒内」要求 |
| 端到端冒烟 | 真实飞书 API：🔧 开工 / ⚙️ read_file / ⚙️ execute_code / ✅ 完工 共 4 条；第 3 条 ⚙️ 被抑制；GLANCE 被 DONE 替换 |
| 重启方式 | `systemd-run --user --unit=mimir-feishu-ux-restart`（独立 cgroup）+ 脚本内 sleep 150s，避免杀掉当前飞书轮 |

验收读数对照：① `grep -c reaction gateway/platforms/feishu_adapter.py` = 见下方 grep 输出（≥3）② 刘哥发消息 1 秒内见表情（刘哥亲眼=终验）③ 三段播报已实测 ④ 单轮播报 = 4 条（=封顶值，未超）
