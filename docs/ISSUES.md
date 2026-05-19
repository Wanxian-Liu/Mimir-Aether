# ISSUES

> 创建：2026-05-16 · 会话 #72 · 刘哥要求建

---

## #1 — 图片接收失败（Bug A）

| 字段 | 内容 |
|------|------|
| 优先级 | 🔴 高 |
| 症状 | 刘哥在飞书发图片，我看不到。飞书适配器报 "图片下载失败，请重试" |
| 错误码 | HTTP 400（2 次，image_key: `img_v3_0211o_361eb7c…` / `img_v3_0211p_bbcd518…`） |
| 根因 | ① 用户图须 `GET /im/v1/messages/{message_id}/resources/{key}?type=image`；误用 `/im/v1/images/{key}`（仅机器人上传图）→ 400。② token 过期时无 Bearer 也会 400 |
| 修复 | P2-1 token 刷新 + 重试；P2-1b 入站图走 message-resource（`message_id` + `image_key`） |
| 状态 | 下载 `resolved`（2026-05-19 `Image downloaded` + message-resource）；识图 `blocked`（缺 OPENROUTER_API_KEY，DeepSeek 纯文本模型无法 vision） |

## #2 — HTML 表格空列名导致消息回退纯文本（Bug B）

| 字段 | 内容 |
|------|------|
| 优先级 | 🟡 中 |
| 症状 | 刘哥看到部分 HTML 消息变成纯文本。飞书错误码 `230099` / `200907` — "table column name is empty" |
| 根因 | `html_to_feishu_card.py` — `_html_table_to_card()` 曾丢弃空列名列，但部分场景仍向飞书传入空字符串列名 → `230099` / `200907` |
| 修复 | `_normalize_table_column_name()`：空/空白/`&nbsp;` 列名 → `"—"`，保留列数与行对齐 |
| 状态 | ✅ **resolved**（PR #5 已合 `23583a9`，代码已验证） |

## #3 — HTML 按钮只显示一个（Bug C）

| 字段 | 内容 |
|------|------|
| 优先级 | 🟡 中 |
| 症状 | HTML 里写了两组按钮（选 A / 选 B），飞书只显示一个按钮 |
| 根因 | `html_to_feishu_card.py` — 按钮提取在列提取之后。按钮在 `<div class="mimir-columns">` 内部，被先剥离了 |
| 修复方向 | 已修复代码（交换按钮提取与列提取顺序），**等待 Gateway 重启生效** |
| 状态 | `fixed-pending-restart`（代码已修，当前 Gateway PID=69532 已于 15:27 重启，可能已生效） |

---

## 历史（已关闭）

| # | 内容 | 状态 |
|---|------|------|
| — | list_capsules 路径修复 | ✅ resolved |
| — | memory 工具冒烟 | ✅ done |
| — | persistent.json 截断根因 | ✅ root-caused |
| — | 存量胶囊迁移 131 .md → .html | ✅ done |
