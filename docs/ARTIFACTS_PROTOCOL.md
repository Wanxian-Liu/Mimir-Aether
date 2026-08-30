# MimirAether Artifacts 协议

> 对标 Claude Artifacts · Karpathy "HTML > Markdown" 理念
> 版本: 0.1 · 2026-05-14

## 1. 什么是 MimirAether Artifact

一个 **可独立渲染的 HTML 片段**，Agent 生成后：

```
Agent 生成 HTML
  ├─→ Feishu: 转为 interactive 卡片（在线即时）
  ├─→ Wiki:   归档到 docs/raw/（持久化 + 可搜索）
  └─→ File:   保存为独立 .html 文件（浏览器可直接打开）
```

## 2. Artifact 生命周期

```
触发 (用户请求可视化/报告/对比/架构图)
  │
  ▼
生成 (Agent 用 HTML 模板生成 artifact)
  │
  ├─→ 即时通道: Feishu Card 发送
  │
  ▼
归档 (自动写入 docs/raw/ + 更新 index.md)
  │
  ▼
引用 (后续会话可通过 wiki 索引检索)
```

## 3. Artifact 格式规范

### 3.1 标记

```html
<!-- MIMIR:HTML_OUTPUT template=dashboard artifact=true -->
<div class="mimir-artifact" id="artifact-2026-05-14-benchmark">
  ...内容...
</div>
<!-- /MIMIR:HTML_OUTPUT -->
```

### 3.2 元数据

| 属性 | 必填 | 说明 |
|------|:----:|------|
| `template` | ✅ | 模板名 (dashboard/report/compare/architecture/demo) |
| `artifact` | ⬜ | `true` 标记为 artifact（触发归档） |
| `id` | ⬜ | 唯一 ID，自动生成为 `artifact-{date}-{slug}` |
| `title` | ⬜ | 标题，默认从 `<h1>` 提取 |

### 3.3 模板类型

| 模板 | 适合场景 | 飞书卡片效果 |
|------|---------|------------|
| `dashboard` | 评测报告、状态总览 | 记分卡 + 进度条 + 表格 |
| `report` | 详细分析报告 | 分段 + 折叠详情 + 发现列表 |
| `compare` | 多对象对比 | 并排对比卡 + 差异高亮 |
| `architecture` | 系统架构图 | CSS Grid 分层 + 数据流 |
| `demo` | 可交互演示 | 折叠面板 + 多列 + 彩色块 |

## 4. 飞书卡片映射

| HTML | 飞书卡片元素 | 视觉效果 |
|------|------------|---------|
| `<h1>` | `header.title` (plain_text) | 蓝色标题栏 |
| `<table>` | `table` 组件 | 原生表格 |
| `<div class="mimir-note">` | `note` 元素 | **黄色背景块** ← 明显区别 |
| `<div class="mimir-columns">` | `column_set` | **并排多列** ← 明显区别 |
| `<div class="mimir-progress">` | 自定义进度条 | ████░░░░ |
| `<details>` | 折叠文本 | 📋 折叠区 |
| `<pre><code>` | `lark_md` 代码块 | 语法高亮 |
| `<button class="mimir-action">` | `action` 按钮 | **可点击按钮** ← 明显区别 |

## 5. 触发规则

| 用户说 | 触发模板 | artifact |
|--------|---------|:--------:|
| "评测/benchmark/评分" | `dashboard` | ✅ |
| "报告/分析/审查" | `report` | ✅ |
| "对比/比较/vs" | `compare` | ✅ |
| "架构/结构/设计" | `architecture` | ✅ |
| "画图/可视化/演示" | `demo` | ✅ |

## 6. 存储路径

```
docs/raw/artifact-{date}-{slug}.html     ← artifact HTML 文件
wiki/index.md                             ← 自动追加索引条目
templates/html/{template}.html            ← 模板文件
```

## 7. 与 Claude Artifacts 的差距

| 能力 | Claude | MimirAether | 差距原因 |
|------|:------:|:-----------:|---------|
| 实时渲染 | 侧面板 iframe | 飞书卡片 | 飞书无原生 iframe |
| 交互性 | 完整 JS | 飞书 Action 按钮 | 飞书沙盒限制 |
| 版本管理 | Artifacts 面板 | Wiki 归档 | 功能等价 |
| 导出 | 下载 | 独立 .html 文件 | 功能等价 |
| 多设备 | Web | 飞书跨设备 | 飞书优势 |

## 8. 演进路线

```
v0.1: 静态 HTML → 飞书卡片（当前）
v0.2: 飞书 Action 按钮（可交互）
v0.3: 多列布局 + 彩色块
v0.4: 文件预览链接（HTML→浏览器）
v1.0: 完整 Artifacts 体验
```
