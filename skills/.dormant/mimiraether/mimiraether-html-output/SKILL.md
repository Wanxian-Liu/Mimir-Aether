---
name: mimiraether-html-output
description: MimirAether HTML 双模输出——复杂报告、评测、架构图等场景自动切换 HTML 输出。对齐 Karpathy "HTML > Markdown" 理念。
version: 1.0.0
category: mimiraether
tags: [html, output, rendering, feishu-card, artifacts, karpathy]
---

# mimiraether-html-output

## 触发规则

### 自动触发（HTML 模式）

| 触发条件 | HTML 模板 |
|----------|----------|
| 评测/基准测试结果 | `dashboard` |
| 架构图/流程图 | `architecture` |
| 多对象对比 (≥3 维度) | `compare` |
| 代码审查报告 | `report` |
| Pipeline 状态总览 | `dashboard` |
| 用户说"画个XX图" / "可视化" | `architecture` |
| 数据 > 5行表格 | `compare` (可排序表) |

### 保持 Markdown（不切换）

| 条件 | 理由 |
|------|------|
| 简短问答 (<200字) | HTML 开销不划算 |
| 纯文本指令 | 无渲染需求 |
| 代码片段 | 飞书 lark_md 足够 |
| 用户在终端模式 | HTML 无法渲染 |

## 输出格式约定

当触发 HTML 模式时，输出包装为：

```html
<!-- MIMIR:HTML_OUTPUT template=dashboard -->
<div class="mimir-report">
  ... HTML content ...
</div>
<!-- /MIMIR:HTML_OUTPUT -->
```

包装标记 `MIMIR:HTML_OUTPUT` 让下游处理器（飞书桥接、Wiki 归档）识别这是一个 HTML 块。

## 模板索引

| 模板 | 文件 | 用途 |
|------|------|------|
| `dashboard` | `templates/html/dashboard.html` | 评测结果、Pipeline 状态、指标面板 |
| `report` | `templates/html/report.html` | 代码审查、项目总结、分析报告 |
| `compare` | `templates/html/compare.html` | Agent 对比、方案对比、多维对比表 |
| `architecture` | `templates/html/architecture.html` | 架构图、流程图、关系图（CSS Grid） |

## 下游处理器

```
Agent 输出 HTML 块
     │
     ├─→ 飞书: html_to_feishu_card.py → Card JSON → send_message
     ├─→ Wiki: 嵌入 .md 或保存到 wiki/raw/*.html
     └─→ 终端: 降级为 Markdown 摘要 + 文件路径
```

## 与现有 Pipeline 集成

HTML 输出在 Pipeline 的 **输出阶段** 触发：

```
brainstorming → strategic-planner → plan-mode → execute
                                                    │
                              ┌─────────────────────┘
                              ▼
                         evaluator-optimizer
                              │
                    ┌─────────┴─────────┐
                    ▼                   ▼
              Markdown 输出        HTML 输出
              (简单回复)           (复杂报告/可视化)
```

## 模板使用示例

### 评测报告 → dashboard

```
用户: "跑一下 benchmark 对比 MimirAether 和 Hermes"
Agent:
  1. 执行 benchmark
  2. scorer.py 产生分数
  3. 检测: 评测结果 + ≥3维度 → 触发 HTML dashboard
  4. 输出 HTML 仪表盘 (进度条 + 雷达图 + 差异分析)
```

### 架构图 → architecture

```
用户: "画一下 MimirAether 的 Pipeline 架构"
Agent:
  1. brainstorming 确认范围
  2. 检测: 架构图请求 → 触发 HTML architecture
  3. 输出 CSS Grid 架构图 (可缩放 + 可点击模块详情)
```
