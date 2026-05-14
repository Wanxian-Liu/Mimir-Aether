# C3 Implementation Plan: 飞书多模态交互

**Created**: 2026-05-12
**Status**: executing

## Goal

飞书 Bot 能接收并"看懂"图片消息 — 用户拍图发给 Bot，Bot 下载图片并调用视觉模型分析。

## Assumptions

1. 视觉模型可用（GPT-4o/Claude 3.5 等已配置的 provider）
2. 非视觉模型回退：描述"收到1张图片，但我当前模型不支持视觉"
3. Feishu API `GET /open-apis/im/v1/images/{image_key}` 可下载

## Task Breakdown

### Task 1: Feishu Adapter — 图片消息检测与下载 (~25 min)

**Files**: `gateway/platforms/feishu_adapter.py`

变更内容：
1. `_event_dict_to_message_event` 新增 `msg_type=image` 检测
2. 提取 `image_key`（从 content JSON）
3. 新增 `_download_image(image_key) -> Path` 方法
4. 对图片消息：`message_type=PHOTO`, `media_urls=[local_path]`, `text=""`
5. 保持 text 消息原有逻辑不变

验证：单元测试模拟 feishu image 事件 → 输出正确的 MessageEvent

### Task 2: Feishu Adapter — 图片下载实现 (~15 min)

**Files**: `gateway/platforms/feishu_adapter.py`

变更内容：
1. `_download_image` 使用 `aiohttp` + `tenant_access_token` 调用飞书图片下载 API
2. 保存到 `data/feishu_images/` 目录
3. 错误处理：下载失败时 text fallback "📷 [图片下载失败]"

### Task 3: Agent — 视觉模型图片注入 (~20 min)

**Files**: `agent/core_loop.py`, `agent/prompt_builder.py`

变更内容：
1. `_execute_turn` / `run_conversation` 中检测 `media_urls`
2. 对视觉模型：读取图片 → base64 → 注入 user message 的 `content` 数组
3. 对非视觉模型：注入文本 "📷 用户发送了一张图片，但当前模型不支持视觉识别"
4. 使用 provider 的 `supports_vision` 标志判断

验证：模拟 PHOTO 事件 → agent 能正常处理并回复

## Dependency Graph

```
Task 1 (message detection) → Task 2 (download) → Task 3 (agent injection)
```

All sequential — each depends on the previous.

## Verification

- [ ] `./run_ralph_tier0.sh` 全绿
- [ ] 模拟 feishu image 事件 → feishu_adapter 输出 PHOTO MessageEvent
- [ ] 视觉模型 prompt 中包含 base64 图片数据
