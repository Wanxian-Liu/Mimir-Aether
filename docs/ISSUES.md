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
| 修复方向 | 已修复代码（交换按钮提取与列提取顺序），需 **Gateway 重启** 后加载新代码 |
| 状态 | ✅ **resolved**（2026-05-25 刘哥飞书 T-04 复验：两按钮可见；Gateway PID 135797） |

---

## 历史（已关闭）

| # | 内容 | 状态 |
|---|------|------|
| — | list_capsules 路径修复 | ✅ resolved |
| — | memory 工具冒烟 | ✅ done |
| — | persistent.json 截断根因 | ✅ root-caused |
| — | 存量胶囊迁移 131 .md → .html | ✅ done |

---

## #4 — MimirAether 全方位体检报告（健康检查）

| 字段 | 内容 |
|------|------|
| 优先级 | 🟡 中（多项需改进）|
| 类型 | 健康检查 / 重构记录 |
| 发起 | 2026-06-19 刘哥指示 |
| 对标 | Hermes Agent（`~/.openclaw/projects/hermes-agent/`）|
| 总分 | **7.0/10**（平均）|

### 体检结果汇总

| Part | 主题 | 得分 |
|:---:|------|:----:|
| #4.1 | 基础架构与代码质量 | 6.0 |
| #4.2 | Agent Loop 执行引擎 | 7.3 |
| #4.3 | 上下文压缩与记忆 | 6.9 |
| #4.4 | 工具系统与MCP | 7.1 |
| #4.5 | 模型管理与凭证池 | 7.1 |
| #4.6 | 提示词构建与安全 | 7.9 ⭐ |
| #4.7 | 测试、部署与运维 | 6.5 |

### MimirAether 领先能力

- **智能模型路由**（318行，Part 5）
- **工具质量评估 + 排序**（652行，Part 4）
- **5个独立 Guards**：degeneration_guard / intent_action_guard / skill_path_guard / search_first_guard / verify_before_report_guard（Part 6）
- **Prompt Injection 防护**（Part 6）
- **学术基础扎实**：LeWM 论文（2603.19312）SIGReg + VoE（Part 6）
- **运维脚本丰富**：77个脚本（Part 7）
- **Memory Fence 安全围栏**（Part 3）
- **Provider 生态完整**：registry / runtime / profile / smart_routing（Part 5）

### 关键差距清单

| 优先级 | 问题 | 来源 Part | 建议工作量 |
|:---:|------|:--------:|:---------:|
| P0 | 测试覆盖严重不足（151 vs 1266，8.4倍差距）| Part 7 | 1周 |
| P0 | CI workflows 不足（2 vs 16）| Part 7 | 1周 |
| P1 | 凭证清理系统缺失（缺 `credential_sources.py`）| Part 5 | 1天 |
| P1 | `mcp_tool.py` 2264行单文件 | Part 4 | 1.5天 |
| P1 | `agent/tool_registry.py` 343行死代码 | Part 4 | 半天 |
| P1 | 拆分巨型文件：`trajectory_compressor.py` (1507行) / `batch_runner.py` (1366行) / `mimir_state.py` (1019行) | Part 1 | 2天 |
| P1 | `context_compressor.py` 丢失 ContextEngine ABC 抽象 | Part 3 | 1天 |
| P2 | 缺容器化部署（Docker）| Part 7 | 1天 |
| P2 | `prompt_builder.py` 1827行过大 | Part 6 | 1.5天 |
| P2 | 拆分 `credential_persistence.py` 1130行 | Part 5 | 半天 |

### 状态
- ✅ 体检报告已生成
- ✅ **Cursor 验真**（2026-06-19）：见 [`MIMIR_LIU_CURSOR_BRIDGE.md`](./MIMIR_LIU_CURSOR_BRIDGE.md) §1「ISSUES #4」；整改粒 **HC-01～HC-23**
- ⏳ **改进未开始** — 建议顺序：HC-01 → HC-11 → HC-13 → HC-12；行为轨并行 **IQ55-10e**
