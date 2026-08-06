# [DORMANT] mimiraether-html-output

**沉寂时间**: 2026-07-31T07:38:32.244696+00:00
**原始分类**: general
**描述**: MimirAether HTML 双模输出——复杂报告、评测、架构图等场景自动切换 HTML 输出。对齐 Karpathy "HTML > Markdown" 理念。
**触发阈值**: 60天未触碰

---

## 技能要点

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

## 模板索引

| 模板 | 文件 | 用途 |
|------|------|------|
| `dashboard` | `templates/html/dashboard.html` | 评测结果、Pipeline 状态、指标面板 |
| `report` | `templates/html/report.html` | 代码审查、项目总结、分析报告 |
| `compare` | `templates/html/compare.html` | Agent 对比、方案对比、多维对比表 |
| `architecture` | `templates/html/architecture.html` | 架构图、流程图、关系图（CSS Grid） |

## 飞书集成 + 安全回退

### 当前状态

```
USE_HTML_OUTPUT = False  ← 默认关闭，飞书用 Markdown（跟现在一模一样）
```

### 三级回退链

```
Agent 生成 HTML
     │
     ▼
gateway/html_to_feishu_card.py
     │
     ├─→ [1] 飞书卡片 JSON（优先）
     │     条件: USE_HTML_OUTPUT=True AND HTML 可转换
     │     效果: 表格/进度条/折叠面板 → 飞书原生卡片组件
     │
     ├─→ [2] 降级 Markdown（卡片不支持时）
     │     条件: 部分元素无法转换
     │     效果: HTML → 纯文本 + 飞书 Markdown 子集
     │
     └─→ [3] 原始 Markdown（任何失败时）
           条件: 转换器异常
           效果: 跟现在一模一样 ⬅️ 保底
```

### 快速回退

修改 `gateway/html_to_feishu_card.py` 一行:

```python
USE_HTML_OUTPUT = False  # 改回 False 即恢复纯 Markdown
```

## 下游处理器

```
Agent 输出 HTML 块
     │
     ├─→ 飞书: html_to_feishu_card.py → Card JSON → send_message
     │         └─ 失败 → 自动回退 Markdown
     ├─→ Wiki: 嵌入 .md 或保存到 wiki/raw/*.html
     └─→ 终端: 降级为 Markdown 摘要 + 文件路径
```

## 飞书卡片模板

| 模板 | 文件 | 飞书卡片对应 |
|------|------|-------------|
| `benchmark_card` | `templates/feishu_cards/benchmark_card.json` | 评测结果 |
| `architecture_card` | `templates/feishu_cards/architecture_card.json` | 架构图 |
| `compare_card` | `templates/feishu_cards/compare_card.json` | 方案对比 |

---

> 此胶囊由 Skill Curator 自动生成。原始技能已移入 .dormant/。
> 调用 `skill_view("mimiraether-html-output")` 即可自动唤醒。
