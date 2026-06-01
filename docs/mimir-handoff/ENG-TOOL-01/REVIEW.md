# ENG-TOOL-01: Cursor 复核重点

## 1. 设计合规

- **env guard** `MIMIR_TOOL_EVENTS=1`：默认关闭，零影响
- **subscriber 异常隔离**：每个 callback 独立 try/except，不传播
- **import lazy**：在 `agent_loop.py` 内局部 import，不增加模块加载开销

## 2. 契约匹配

- 不修改 `SESSION_SEARCH_BACKEND`、`AUTO_EVOLVE` 等任何默认值
- 不涉及 `data/persistent.json`
- 不修改生产 env

## 3. 已知未做

- **飞书卡片集成**：`gateway/platforms/feishu_adapter.py` 中 subscribe → 发「工具执行中」卡片是平台侧的事，不在本粒范围内。本粒只提供 emit 基础设施 + 文档。
- **并行工具执行**：PI-L06 #2 仅限于事件流；并行执行（PI-L06 #1 之外的独立任务）未包含。
- **M6**：触达 `agent/` 代码，但仅为轻量 add-only 改动，无实质进化测量点。由 Cursor 复核时决定是否记录。
