# Phase 2 — P2-1 飞书收图（ISSUES #1 / BACKLOG #5）

| 字段 | 值 |
|------|-----|
| **日期** | 2026-05-19 |
| **应用** | **mimiraether**（App ID `cli_aa82adc1…`） |
| **代码** | `gateway/platforms/feishu_adapter.py` |

---

## 1. 现象

- 用户在飞书发图片，Agent 侧显示「图片下载失败，请重试」。
- 日志：`Image download failed: HTTP 400`，`image_key` 形如 `img_v3_0211…`。

## 2. 根因

`_feishu_download_image()` 用同步 `requests.get` 拉取  
`GET /open-apis/im/v1/images/{image_key}`，仅在 `_tenant_token` 存在且未过期时附加 `Authorization`。

入站图片在 `_async_dispatch_p2` → `_event_dict_to_message_event` 路径触发下载。若 token 尚未刷新、已过期，或与 `send()` 的异步刷新不同步，请求无 Bearer → 飞书返回 **400**。

## 3. 改点（最小修复）

1. `_tenant_token_valid()` — 与 `send()` 一致，到期前 **60s** 缓冲。
2. `FeishuAdapter._refresh_token_sync()` — 用 `requests.post` 同步刷新 `tenant_access_token`（避免在运行中的 event loop 上 `run_until_complete` 死锁）。
3. `_ensure_tenant_token_sync()` — 下载前确保 token 有效。
4. `_feishu_download_image()` — 下载前 `ensure`；若首次 GET 为 400/401/403，刷新后重试一次。

## 4. 测试

```bash
cd /home/rayliu/src/MimirAether
python3 -m pytest tests/test_feishu_image_token.py -q
```

## 5. 负责人真机验图（mimiraether）

1. 确认 `~/.mimiraether/.env` 含 `FEISHU_APP_ID` / `FEISHU_APP_SECRET`（勿提交仓库）。
2. 仓库根：`python3 cli.py gateway start`（或重启已有 gateway 进程）。
3. 飞书客户端向 **mimiraether** 应用发一张图片（私聊或已接入群）。
4. 预期：不再出现「图片下载失败」；Agent 能收到图并可走 vision  enrichment（若模型/配置启用）。
5. 失败时查 gateway 日志：`tenant_access_token`、`Image downloaded` 或 `refreshing tenant token`。

---

## 6. 修订

| 日期 | 变更 |
|------|------|
| 2026-05-19 | 初版：P2-1 token 刷新 + 重试 |
