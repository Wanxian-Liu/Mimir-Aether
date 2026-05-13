---
name: dogfood
description: "Web应用系统化探索QA测试 — 通过浏览器工具集自动导航、交互、截图取证、生成结构化Bug报告。"
version: 1.1.0
author: MimirAether (adapted from Hermes Agent)
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [qa, testing, browser, web, dogfood]
    related_skills: []
  mimiraether:
    tags: [qa, testing, browser, web, 测试, 质量保障]
    related_skills: [debugging-hermes-tui-commands]
    synced_from: hermes-agent v2026.5.7
    sync_date: 2026-05-12
    adapted: true
    adapt_notes: "Tester名称已更新为MimirAether；工具签名完全兼容（browser_vision/console等一致）；report模板已本地化"
---

# Dogfood: 系统化Web应用QA测试

## 概述

使用浏览器工具集进行系统化探索式QA测试。导航应用、交互元素、截图取证、生成结构化Bug报告。

## 前置条件

- 浏览器工具集可用：`browser_navigate`, `browser_snapshot`, `browser_click`, `browser_type`, `browser_vision`, `browser_console`, `browser_scroll`, `browser_back`, `browser_press`
- 用户提供目标URL和测试范围

## 输入

用户提供：
1. **目标URL** — 测试入口
2. **范围** — 聚焦哪些区域/功能（或"全站"进行综合测试）
3. **输出目录**（可选）— 截图和报告存放位置（默认：`./dogfood-output`）

## 工作流

五阶段系统化流程：

### Phase 1: 规划

1. 创建输出目录结构：
   ```
   {output_dir}/
   ├── screenshots/       # 证据截图
   └── report.md          # 最终报告（Phase 5生成）
   ```
2. 根据用户输入确定测试范围。
3. 构建大致的站点地图，规划要测试的页面和功能：
   - 首页/着陆页
   - 导航链接（头部、底部、侧栏）
   - 关键用户流程（注册、登录、搜索、结账等）
   - 表单和交互元素
   - 边界情况（空状态、错误页、404）

### Phase 2: 探索

对计划中的每个页面或功能：

1. **导航**到页面：
   ```
   browser_navigate(url="https://example.com/page")
   ```

2. **快照**了解DOM结构：
   ```
   browser_snapshot()
   ```

3. **检查控制台**是否有JavaScript错误：
   ```
   browser_console(clear=true)
   ```
   每次导航和每次重要交互后都要做这一步。静默JS错误是高价值发现。

4. **带标注截图**评估页面并识别交互元素：
   ```
   browser_vision(question="描述页面布局，识别视觉问题、破损元素或可访问性问题", annotate=true)
   ```
   `annotate=true` 在交互元素上叠加编号 `[N]` 标签。每个 `[N]` 映射到 `ref @eN` 供后续浏览器命令使用。

5. **系统化测试交互元素**：
   - 点击按钮和链接：`browser_click(ref="@eN")`
   - 填写表单：`browser_type(ref="@eN", text="测试输入")`
   - 键盘导航测试：`browser_press(key="Tab")`, `browser_press(key="Enter")`
   - 滚动内容：`browser_scroll(direction="down")`
   - 无效输入的表单验证测试
   - 空提交测试

6. **每次交互后检查**：
   - 控制台错误：`browser_console()`
   - 视觉变化：`browser_vision(question="交互后有什么变化？")`
   - 预期与实际行为对比

### Phase 3: 收集证据

对每个发现的问题：

1. **截取问题截图**：
   ```
   browser_vision(question="捕获并描述此页面上可见的问题", annotate=false)
   ```
   保存响应中的 `screenshot_path` — 报告中将引用它。

2. **记录详情**：
   - 问题发生的URL
   - 复现步骤
   - 预期行为
   - 实际行为
   - 控制台错误（如有）
   - 截图路径

3. **分类问题**（见 `references/issue-taxonomy.md`）：
   - 严重性：Critical / High / Medium / Low
   - 类别：Functional / Visual / Accessibility / Console / UX / Content

### Phase 4: 归类

1. 审核所有收集的问题。
2. 去重 — 合并同一bug在不同位置表现的问题。
3. 为每个问题分配最终严重性和类别。
4. 按严重性排序（Critical优先，然后High、Medium、Low）。
5. 按严重性和类别统计问题数量，用于执行摘要。

### Phase 5: 报告

使用 `templates/dogfood-report-template.md` 模板生成最终报告。

报告必须包含：
1. **执行摘要**：总问题数、按严重性细分、测试范围
2. **每问题章节**：
   - 问题编号和标题
   - 严重性和类别徽章
   - 发现URL
   - 问题描述
   - 复现步骤
   - 预期vs实际行为
   - 截图引用（使用 `MEDIA:<screenshot_path>` 内联图片）
   - 相关控制台错误
3. **所有问题汇总表**
4. **测试说明** — 测试了哪些、未测试哪些、任何阻塞

保存报告到 `{output_dir}/report.md`。

## 工具参考

| 工具 | 用途 |
|------|------|
| `browser_navigate` | 跳转到URL |
| `browser_snapshot` | 获取DOM文本快照（无障碍树） |
| `browser_click` | 通过ref（`@eN`）或文本点击元素 |
| `browser_type` | 在输入框中输入文本 |
| `browser_scroll` | 在页面上向上/向下滚动 |
| `browser_back` | 浏览器后退 |
| `browser_press` | 按下键盘按键 |
| `browser_vision` | 截图 + AI分析；使用 `annotate=true` 标注元素 |
| `browser_console` | 获取JS控制台输出和错误 |

## 提示

- **每次导航和重要交互后都要检查 `browser_console()`。** 静默JS错误是最有价值的发现之一。
- **当需要对交互元素位置进行推理或快照ref不清晰时，使用 `annotate=true` 配合 `browser_vision`。**
- **同时测试有效和无效输入** — 表单验证bug很常见。
- **滚动长页面** — 折叠线以下的内容可能有渲染问题。
- **测试导航流程** — 端到端点击多步流程。
- **注意截图中可见的布局问题来检查响应式行为。**
- **不要忘记边界情况**：空状态、超长文本、特殊字符、快速点击。
- 向用户报告截图时包含 `MEDIA:<screenshot_path>`，以便内联查看证据。
