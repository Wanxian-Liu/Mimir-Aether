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
| "推到 git"/"commit"/"push"/"发布" | `mimiraether-ship` | 预发布检查+推送 |
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
| 5 | `mimiraether-cross-session` | 记忆 | 跨会话, 上次 | 跨会话记忆自动恢复 |
| 6 | `mimiraether-capsule-factory` | 知识 | 胶囊 | Capsule 知识工厂 |
| 7 | `mimir-true-self` | 铁律 | 真我, 身份, 独立 | 自我认知与根因 |
| 8 | `mimiraether-self_health_check` | 自进化 | 健康, 状态 | 自我维护检查 |
| 9 | `mimiraether-brainstorming` | 规划 | brainstorm, 想想 | 事前多头分析 |
| 10 | `mimiraether-html-output` | 输出 | html, 报告 | HTML 双模输出 |
| 11 | `mimiraether-personal-assistant` | 用户 | 记录, 保存, 记住 | 自动分类存储用户信息 |
| 12 | `mimiraether-heartbeat` | 铁律 | 醒来, 唤醒 | 身份三问+基调 |
| 13 | `mimiraether-verification` | 铁律 | 验证, verify | 收尾硬门控 |
| 14 | `mimiraether-context-compressor` | 运维 | 压缩, context | 上下文压缩管理 |
| 15 | `mimiraether-root-cause-debugging` | 调试 | debug, 根因, 为什么会 | 四阶段根因分析 |
| 16 | `mimiraether-context-engine` | 运维 | context 引擎 | 对话上下文管理 |
| 17 | `mimiraether-auto-load` | 元 | — | 自动加载入口 |
| 18 | `mimiraether-skill-prune` | 技能 | prune, 清理 | 无用技能清除 |
| 19 | `mimiraether-ship` | 发布 | ship, 发布, commit | 结构化发布流程 |
| 20 | `mimiraether-study-tree` | 学习 | 学习, 论文, 研究 | 知识研究树 |
| 21 | `mimiraether-physics-reasoner` | 推理 | 物理, 推理 | 物理世界推理 |
| 22 | `mimiraether-self_evolution` | 自进化 | 进化, 智商, 成长 | 三环自我进化 |

---

## 路由决策树

```
用户输入
  ↓
① 检查 dispatching-parallel-agents 的触发词
   → 匹配 → 并行分发
  ↓
② 检查 路由表（路由此表）
   → 匹配 → 加载对应 skill(es)
  ↓
③ 检查 通用触发
   → 匹配 → 加载
  ↓
④ 无匹配 → 加载 mimiraether-tool-triggers + mimiraether-self_health_check
   → 自检通过后，用基础能力响应
```

---

## 3 条核心操作规则

| # | 规则 | 为什么 |
|:-:|:----|:------|
| 1 | **不要静默加载** | 加载哪个 skill，在你的思考中说明选择和理由。不在用户面前隐藏路由决策 |
| 2 | **路由失败时，先自检再响应** | 无匹配时，先加载 tool-triggers + self_health_check 自检，再响应。不自检就回答是跑偏常见入口 |
| 3 | **能路由到确切 skill 就不要回退到"通用"** | 即使触发词不完全匹配，关键词匹配到唯一 skill 时直接加载。回退只在多 skill 平权时使用 |
