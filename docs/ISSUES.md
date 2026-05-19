# ISSUES

> 创建：2026-05-16 · 会话 #72 · 刘哥要求建

---

## #1 — 图片接收失败（Bug A）

| 字段 | 内容 |
|------|------|
| 优先级 | 🔴 高 |
| 症状 | 刘哥在飞书发图片，我看不到。飞书适配器报 "图片下载失败，请重试" |
| 错误码 | HTTP 400（2 次，image_key: `img_v3_0211o_361eb7c…` / `img_v3_0211p_bbcd518…`） |
| 根因 | `feishu_adapter.py:101` — `_feishu_download_image()` 用 `requests.get()` 同步下载，依赖 `adapter._tenant_token` 做认证。token 过期或未初始化时，请求不带 Authorization header → 飞书返回 400 |
| 修复方向 | 给 `_feishu_download_image` 加 token 刷新逻辑，或改用 aiohttp 异步 |
| 状态 | `fixed-pending-verify`（P2-1：下载前 `_ensure_tenant_token_sync` + 一次重试；见 `docs/phase2/P2-1-feishu-image.md`） |

## #2 — HTML 表格空列名导致消息回退纯文本（Bug B）

| 字段 | 内容 |
|------|------|
| 优先级 | 🟡 中 |
| 症状 | 刘哥看到部分 HTML 消息变成纯文本。飞书错误码 `230099` / `200907` — "table column name is empty" |
| 根因 | `html_to_feishu_card.py:98` — `_html_table_to_card()` 过滤空列名时只检查全部为空才跳过。部分列名为空时，空字符串传给飞书卡片 API → 渲染失败 → adapter 回退 plain text |
| 修复方向 | 空列名替换为 "—"，或限制仅过滤空列 |
| 状态 | `open` |

## #3 — HTML 按钮只显示一个（Bug C）

| 字段 | 内容 |
|------|------|
| 优先级 | 🟡 中 |
| 症状 | HTML 里写了两组按钮（选 A / 选 B），飞书只显示一个按钮 |
| 根因 | `html_to_feishu_card.py` — 按钮提取在列提取之后。按钮在 `<div class="mimir-columns">` 内部，被先剥离了 |
| 修复方向 | 已修复代码（交换按钮提取与列提取顺序），**等待 Gateway 重启生效** |
| 状态 | `fixed-pending-restart` |

---

## 历史（已关闭）

| # | 内容 | 状态 |
|---|------|------|
| — | list_capsules 路径修复 | ✅ resolved |
| — | memory 工具冒烟 | ✅ done |
| — | persistent.json 截断根因 | ✅ root-caused |
| — | 存量胶囊迁移 131 .md → .html | ✅ done |
