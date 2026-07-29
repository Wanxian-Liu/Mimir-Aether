# [DORMANT] mimiraether-html-output

**沉寂时间**: 2026-07-29T08:22:40.155584+00:00
**原始分类**: root
**描述**: MimirAether HTML 双模输出——复杂报告、评测、架构图等场景自动切换 HTML 输出。对齐 Karpathy "HTML > Markdown" 理念。
**触发阈值**: 60天未触碰

---

## 技能要点

# MimirAether HTML 双模输出

## 核心原则

> "HTML is a proper standard with a real spec. LLMs are trained on the web. Just output HTML." — Karpathy

当内容超过简单问答时，输出 HTML 而非 Markdown。HTML 模板 → 飞书卡片 / Wiki 页面 / 独立文件。

## 触发规则

| 用户意图 | 模板 | artifact |
|---------|------|:--------:|
| 评测/benchmark/评分 | `dashboard` | ✅ |
| 分析报告/代码审查 | `report` | ✅ |
| 对比/比较/vs | `compare` | ✅ |
| 架构/结构/设计 | `architecture` | ✅ |
| 画图/可视化/演示 | `demo` | ✅ |

## 输出格式

```html
<!-- MIMIR:HTML_OUTPUT template=dashboard artifact=true -->
<div class="mimir-artifact">
  ...内容...
</div>
<!-- /MIMIR:HTML_OUTPUT -->
```

## 飞书特有组件（明显视觉差异）

使用这些 class 可触发飞书卡片原生组件：

| HTML | 飞书效果 | 
|------|---------|
| `<div class="mimir-note">text</div>` | **黄色背景 note 块** |
| `<div class="mimir-columns"><div class="mimir-col">A</div><div class="mimir-col">B</div></div>` | **并排多列** |
| `<button class="mimir-action">按钮</button>` | **可点击按钮** |
| `<table>...</table>` | 原生表格 |
| `<div class="mimir-progress">80%</div>` | 进度条 |

## 下游处理链

```
Agent 输出 HTML
  ├─→ 飞书: html_to_feishu_card.py (USE_HTML_OUTPUT=True)
  ├─→ Wiki: 自动归档到 wiki/raw/artifact-{date}-{slug}.html
  └─→ File: 保存独立 .html 文件
```

## 模板文件

| 模板 | 路径 |
|------|------|
| 仪表盘 | `templates/html/dashboard.html` |
| 报告 | `templates/html/report.html` |
| 对比 | `templates/html/compare.html` |
| 架构图 | `templates/html/architecture.html` |

---

> 此胶囊由 Skill Curator 自动生成。原始技能已移入 .dormant/。
> 调用 `skill_view("mimiraether-html-output")` 即可自动唤醒。
