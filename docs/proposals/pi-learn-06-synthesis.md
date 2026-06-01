# PI-L06: 复盘合成 — 3 条可立项改进（≤1 页）

> 复盘自 pi-agent 5 个模块的只读学习（PI-L01~L05），提炼可立项的改进建议。

---

## 总体印象

pi-agent 和 MimirAether 在核心架构上高度一致（LLM↔tool 交替循环、JSONL 会话持久化、多 provider 抽象、跨会话上下文注入）。差异主要体现在：

- **pi 以事件驱动 + TUI 终端为主**，架构更灵活但更复杂
- **Mimir 以同步状态机 + 飞书/Telegram 等聊天平台为主**，架构更稳定但灵活性较低

---

## 3 条可立项改进（按优先级）

### 1. 统一测试 Harness（中优先级 · 2–3 天）

**来源**：PI-L05 — pi 的 `createHarness()` 工厂 + `FauxProvider`。

Mimir 当前测试分散在 15+ 个文件，每个手动 `SessionDB(tmp_path)` + `import` 被测函数。无统一 mock LLM provider，依赖 `unittest.mock.patch`。

**做法**：
- `tests/conftest.py` 加 `create_mimir_harness()` 工厂，返回 `Harness` 对象（含自动 `tmp_path`、内存 `SessionDB`、`mock_llm`、`event_collector`、`cleanup`）
- 实现轻量 `FauxLlmProvider`，支持 `set_responses([...])` 精确控制 LLM 输出序列
- 迁移 2–3 个现有测试用例示范用法

**收益**：减少测试样板 40%+，新测试可 5 行内完成 setup-assert-cleanup。

---

### 2. 工具执行事件流（低优先级 · 1–2 天）

**来源**：PI-L02 — pi 的 `tool_execution_start/update/end` 实时事件。

Mimir 当前 `execute_tool_call` 是黑盒循环——工具开始执行和完成的结果只记录 JSONL，无实时投递。用户（飞书/Telegram）看不到工具执行进度。

**做法**：
- `execution_pipeline.py` 中 `record_tool_call` 加 `tool_execution_start` / `tool_execution_end` emit（模块内 event bus）
- gateway 端检测这些事件，可选投递给飞书卡片更新

**收益**：长工具调用（如 30s+ 的代码执行）用户可见进度而非卡住感。

---

### 3. `--one-shot` CLI 模式（低优先级 · 1 天）

**来源**：PI-L03 — pi 的 Print 模式。

Mimir CLI 目前只做交互式 shim。`python -m mimir_cli "prompt"` 无法单次调用后退出。

**做法**：
- `cli.py` 加 `--one-shot` / `-o` flag：接受 inline prompt → 执行一个 turn → 打印结果 → 退出
- 方便 script/CI 集成

**收益**：降低脚本/自动化集成门槛，无需启动全交互会话。

---

## 不立项（明确不做）

| 建议 | 原因 |
|------|------|
| OAuth 认证流 | Mimir 生产固定 DeepSeek/Anthropic API key，无订阅集成需求 |
| 分叉/会话树 | 生产 session 单向线性，无 UI 支持分支 |
| 36+ provider 全覆盖 | Mimir 只需 3–4 个 provider，维护负担 > 收益 |
| steerr/followUp 队列 | 聊天平台消息模型不支持用户不可见的中途注入 |
