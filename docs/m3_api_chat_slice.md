# M3 垂直切片：OpenAI 兼容 Chat HTTP

## 场景

HTTP 客户端向本地 API 发送 OpenAI 形请求：

- `POST /v1/chat/completions`
- 请求体含 `model`、`messages`、`stream: false`
- 处理器从消息中取最后一条 **user** 文本，调用 `MimirAetherAgent.run_conversation(user_message)`，将返回写入 `choices[0].message.content`。

实现：`api_service.py`（`create_app()` → aiohttp `Application`）。

## 自动化验收（无网、桩 LLM）

测试文件：`agent/test_m3_api_chat_slice.py`

- 使用 **`aiohttp.test_utils.TestClient` + `TestServer`** 挂载 `api_service.create_app()`。
- 对 **`MimirAetherAgent._call_model_with_tokens`** 打桩；**`_restore_session`** 关闭，与 Tier-1 / CLI M3 一致。
- **`GET /health`**：仅校验 200 与 `status` / `service`。
- **`POST /v1/chat/completions`**：断言 `object`、`model`、`choices[0].message` 与桩回复子串。
- Checkpoint 目录隔离到 pytest `tmp_path`；每测前重置 **`AgentManager` 单例**，避免会话间泄漏。

运行：

```bash
python3 -m pytest -q agent/test_m3_api_chat_slice.py
```

纳入默认门禁：`./run_ralph_tier0.sh`（Gate2 列表）。

## 与 CLI 切片的关系

- 第一条 M3：`docs/m3_cli_quick_task_slice.md`（`cli.run_task` / `python cli.py -q`）。
- 第二条（本文）：**同一 agent 栈**，入口为 HTTP 而非 CLI。

## 修订

| 日期 | 说明 |
|------|------|
| 2026-05-02 | 初版：TestClient + 非流式 chat + Ralph Gate2。 |
