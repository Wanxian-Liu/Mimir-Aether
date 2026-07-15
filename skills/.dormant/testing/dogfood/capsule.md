# [DORMANT] dogfood

**沉寂时间**: 2026-07-14T18:58:41.620494+00:00
**原始分类**: testing
**描述**: Web应用系统化探索QA测试 — 通过浏览器工具集自动导航、交互、截图取证、生成结构化Bug报告。
**触发阈值**: 60天未触碰

---

## 技能要点

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
4. 

... (truncated)

---

> 此胶囊由 Skill Curator 自动生成。原始技能已移入 .dormant/。
> 调用 `skill_view("dogfood")` 即可自动唤醒。
