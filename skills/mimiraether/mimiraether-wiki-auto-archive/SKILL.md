---
description: 当对话浮现可复用知识时自动归档到 wiki。覆盖 learnings 引用 + 追问深层原理 + 技术决策。触发权在 Agent，无需用户指令。L1 自动 / L2 询问。
---

# mimiraether-wiki-auto-archive

## 触发体系（分级）

### L1 — 自动触发（零确认，直接落）

| 触发条件 | 示例 |
|----------|------|
| 从 `learnings/` 搜到知识回答用户 | "Hermes context engine 怎么设计的？" |
| **追问深度 ≥ 2 轮** — 用户对同一话题连续追问，AI 解释了深层原理 | "为什么 WebSocket 卡死？" → "那怎么防止？" → 归档 |
| 明确的技术决策或设计模式 | "类型强制层为什么这样设计？" |

### L2 — 询问确认（一句征求，用户点头就落）

| 触发条件 | 示例 |
|----------|------|
| 一次性参考资料有长期价值 | "这个 GitHub issue 要点要存吗？" |
| 工具/平台 API 的 quirks 或坑 | "飞书 API 这个限制值得记吗？" |
| 用户明确说"记住这个" | 直接升级到 L1 自动 |

### 不触发

| 条件 | 理由 |
|------|------|
| 一句话问答 | 无沉淀价值 |
| 临时调试/日志 | 时效性短 |
| 纯闲聊 | 不相关 |
| 已有 wiki 页覆盖 | 去重 |

## 工作流

```
L1: 引用/追问 → 回答 → 自动落 wiki → 一行告知
L2: 引用 → 回答 → 问一句 → 落或跳过
```

## 归档目标

| 内容类型 | 落点 |
|----------|------|
| Hermes 模块/组件分析 | `~/wiki/entities/hermes-{name}.md` |
| 架构概念/设计模式 | `~/wiki/concepts/{name}.md` |
| Mimir vs Hermes 对比 | `~/wiki/comparisons/{name}.md` |
| 决策记录 | `~/wiki/concepts/decision-{name}.md` |
| 深层技术原理 (L1追问) | `~/wiki/concepts/{name}.md` |
| 工具/平台 quirks | `~/wiki/entities/{tool}-{quirk}.md` |
| 故障诊断经验 | `~/wiki/concepts/troubleshooting-{name}.md` |
| **HTML 报告/仪表盘** | `~/wiki/raw/{name}-{date}.html` |
| **HTML 模板** | `~/wiki/templates/html/{name}.html` |

### HTML 归档规则 (new)

```
触发条件（L1 自动）:
  - Agent 输出含 <!-- MIMIR:HTML_OUTPUT --> 标记
  - 评测/基准测试/架构图/对比报告

落盘:
  1. HTML 源文件 → ~/wiki/raw/{type}-{date}.html
  2. Markdown 摘要页 → ~/wiki/raw/{type}-{date}.md (可选)
  3. 更新 ~/wiki/index.md HTML Reports 节

命名规范:
  benchmark-2026-05-14.html
  architecture-hwm-pipeline.html
  compare-mimir-vs-hermes.html
```

## 页面模板

```markdown
---
title: {标题}
created: {日期}
updated: {日期}
type: entity | concept | comparison
tags: [{领域}]
sources: [learnings/{源文件名}]
---

## 概述
{一句话}

## 核心要点
{从 learnings 或对话提取的关键信息}

## 关联
{与 MimirAether/其他模块/相关概念的关系}
```

## 完成后

追加到 `~/wiki/log.md`：
```
## [{日期}] auto-archive | {页面名} ← {来源: learnings/xxx 或 对话追问}
```

更新 `~/wiki/index.md` 对应节。

## 告知格式

归档完成后简单告知（一行）：
```
📝 wiki: {页面名} ← {来源}
```
