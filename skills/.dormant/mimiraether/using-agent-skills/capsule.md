# [DORMANT] using-agent-skills

**沉寂时间**: 2026-09-27T19:24:43.915228+00:00
**原始分类**: mimiraether
**描述**: 元技能 — 用户意图到正确技能的路由表。当用户说修 bug/写代码/审查一下/写文档时，判定应加载哪个具体技能，避免多个技能并列时无从选择的瘫痪状态。
**触发阈值**: 60天未触碰

---

## 技能要点

# using-agent-skills

**元技能 — 用户意图 → 正确技能路由**

`auto_load: true` · `priority: 0`

当你说"修 bug"、"写代码"、"审查一下"、"写文档"时，此技能自动判定应加载哪个具体技能。避免 22 个技能并列时无从选择的瘫痪状态。

---

## 路由此表

| 你说 | 加载 | 原因 |
|:----|:----|:-----|
| "修 bug"/"debug"/"报错"/"失败"/"不对" | `mimiraether-root-cause-debugging` | 四阶段根因分析，禁止未定位就修 |
| "review"/"审查"/"CR"/"检查" | `requesting-code-review` → `receiving-code-review` | 先送审，再收反馈 |
| "写代码"/"实现"/"改逻辑"/"feature" | `mimiraether-brainstorming` → `writing-plans` → `executing-plans` | 先规划再写 |
| "写文档"/"记录"/"更新" | `mimiraether-skill-solidify` 或 `mimiraether-personal-assistant` | 固定经验或记录事实 |
| "评测"/"benchmark"/"对比"/"vs"/"评分" | `mimiraether-agent-benchmark` | 外部评测方法论 |
| "复盘"/"回顾"/"上次"/"历史"/"还记得" | `mimiraether-cross-session` + `session_search` | 跨会话恢复 |
| "蒸馏"/"压缩"/"梦境"/"memory 整理" | `mimiraether-distillation-execution` | 完整蒸馏流程 |
| "状态"/"健康"/"检查"/"验证" | `mimiraether-self_health_check` + `mimiraether-verification` | 先检再报 |
| "进化"/"智商"/"变聪明"/"成长" | `mimiraether-self_evolution` | 固定进化循环 |
| "技能"/"skill"/"写个技能" | `mimiraether-skill-solidify` | 技能创作流程 |
| "tmd"/"为什么"/"又错了"/"你干了什么" | `mimiraether-root-cause-debugging` + `mimiraether-verification` | **根因+验证双加载** |
| "学习"/"研究"/"论文"/"看" | `mimiraether-study-tree` | 研究树查询 |
| "整理技能"/"清理"/"prune" | `mimiraether-skill-prune` + `mimiraether-skills-hub` | 技能清理流程 |

### 通用触发（不匹配时）

| 关键词 | 加载 |
|:------|:-----|
| 代码路径/函数名/类名 | `mimiraether-root-cause-debugging` |
| 包含 "为什么"/"怎么会" | `mimiraether-root-cause-debugging` |
| 用户情绪（"又"/"你最好"/"认真"） | `mimiraether-verification` + 自检 |
| 什么都没匹配到 | 加载 `mimiraether-tool-triggers` + `mimiraether-self_health_check` |

---

## 22 技能注册表

| # | 名称 | 分组 | 触发词 | 一句话 |
|:-:|:----|:----|:------|:-------|
| 1 | `mimiraether-ralph-core` | 铁律 | ralph, 主线 | Ralph 模式核心约束 |
| 2 | `mimiraether-distillation-execution` | 自进化 | 蒸馏, 梦境, compress | 梦境记忆蒸馏完整流程 |
| 3 | `mimiraether-tool-triggers` | 铁律 | — | 工具触发规则和守卫 |
| 4 | `mimiraether-skill-solidify` | 技能 | 固化, 技能 | 可复用经验固化为 skill |
| 5 | `mimiraether-cross-session` 

... (truncated)

---

> 此胶囊由 Skill Curator 自动生成。原始技能已移入 .dormant/。
> 调用 `skill_view("using-agent-skills")` 即可自动唤醒。
