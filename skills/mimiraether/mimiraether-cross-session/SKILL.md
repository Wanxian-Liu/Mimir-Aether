---
auto_load: false
auto_load_meta:
  triggers:
  - 会话启动
  - 跨会话
  - 持久化
  - 记忆
  - persistent
  - memory
  priority: highest
  description: 每次会话启动时自动加载，确保跨会话记忆自动恢复
description: 每次会话启动时自动加载，确保跨会话记忆自动恢复
---


# mimiraether-cross-session

## name

MimirAether Cross-Session — 跨会话持久化

## description

实现MimirAether在多个会话之间的状态持久化和信息共享。包括用户偏好跨会话保持、项目上下文延续和未完成任务的状态恢复。

## 核心原理

跨会话记忆的核心不是"记住一切"，而是**只记住下个会话启动时最需要的东西**。

三环过滤：
1. **什么值得记** → 只有影响未来决策的才记（偏好、决策、未完成任务）
2. **什么不值得记** → 不记过程日志、已完成任务细节、临时状态
3. **什么该过期** → 完成的任务自动移除、超过3次会话未引用的记忆归档

## 自动注入路径

每次会话启动时，按以下顺序恢复跨会话状态：

```
Step 1: 读取 data/persistent.json（会话状态）
  ├── identity → 确认"我是谁"
  ├── memory.key_decisions → 恢复关键决策
  ├── memory.user_preferences → 恢复用户偏好
  ├── progress.pending_tasks → 恢复未完成任务
  └── progress.completed_milestones → 确认已完成项

Step 2: 自动注入到系统提示
  ├── 将 key_decisions 注入为"已知决策"
  ├── 将 pending_tasks 注入为"待完成"
  └── 将 user_preferences 注入为"用户偏好"
```

## ⚠️ 耐久真源机制（ground_truth.json）

**已知陷阱**：`persistent.json` 会被运行时 `end_session()` 从内存覆盖磁盘，导致会话中直接 patch 的修改丢失。

**解决方案**：`data/ground_truth.json` 是独立于运行时的耐久真源。运行时不会触碰此文件。

### 启动时调和流程

```
Step 0: 读取 data/ground_truth.json（耐久真源，优先）
  ├── current_objective → 当前目标（不被运行时覆盖）
  ├── active_projects → 项目状态
  ├── critical_patterns → 关键经验教训
  └── next_actions → 下一步行动

Step 1: 读取 data/persistent.json（运行时快照）
  ├── 如果 ground_truth 存在且 persistent 的 current_objective 与它不一致
  │   └── 以 ground_truth 为准，并尝试回写 persistent（patch 补救）
  ├── 如果 ground_truth 不存在
  │   └── 仅用 persistent（降级模式）
  └── session_count / curator_nudge / dormant_skills 等运行时指标
      仍以 persistent 为准（这些只有运行时能维护）
```

### 写入规则

| 数据类型 | 写入目标 | 原因 |
|----------|----------|------|
| 运行时指标（session_count, curator_nudge） | persistent.json | 只有运行时能维护 |
| 项目进度（objective, milestones） | **ground_truth.json（主）** + persistent.json（镜像） | 防止被覆盖 |
| 关键决策、learned_patterns | persistent.json（已有） + ground_truth.json（新增模式） | 双写保险 |
| 用户偏好 | persistent.json | 一次性写入，后续只读 |

## 核心功能列表

- **偏好持久化**：保存和恢复用户的交互偏好、工具设置和常用配置
- **项目状态延续**：跨会话追踪项目进度、待办事项和决策历史
- **任务恢复**：中断任务自动保存状态，下个会话可继续执行
- **会话历史检索**：通过session_search搜索跨会话历史记录
- **上下文传递**：将重要上下文从上一会话传递到新会话
- **增量同步**：轻量级状态同步，避免重复加载大型数据
- **差异检测**：自动检测版本变化和会话丢失
- **过期机制**：超过3次会话未引用的记忆自动归档

## 🧠 Wiki 自动维护（Session 68+ 新增）

**问题**：`~/wiki/` 目录结构于5月10日搭建完成，但从未使用——因为触发责任在用户身上。

**解决方案**：触发权移交给 Agent。每次会话启动时自动巡检 wiki。

### 启动时 wiki 巡检

```
Step W0: 读取 ground_truth.json → wiki 节 (status, last_check, pending_ingest)
Step W1: 如果 wiki.status == "empty" 且 learnings/ 有内容
  └── 主动提醒：wiki 空置，learnings 有 N 份笔记待归档
Step W2: 如果 wiki.status == "active"
  └── 读取 SCHEMA.md + index.md → 扫描新 learnings → 标记
```

### 会话中自动归档（rbac: Agent）

当 Agent 从 `learnings/` 引用知识回答用户问题时：
1. 回答完毕后自动判断是否值得 wiki 化
2. 值得：在 `~/wiki/concepts/` 或 `entities/` 创建/更新页面
3. 更新 `index.md` 和 `log.md`
4. 完成后一行告知（不打断对话流）

**归档标准**：明确被问的概念/模块 ✅ | 跨会话复用决策 ✅ | 一次性问答 ❌

## 🧠 V-JEPA 2.1 记忆自检（Session 75+）

**来源**: V-JEPA 2.1 (2603.14482) 深层自监督 — 每层记忆加独立质检
**协议**: `docs/MEMORY_SELF_CHECK.md`

### Layer 2 Cross-Session 自检

每次 `save()` 后自动执行:

```
1. 决策追溯性: key_decisions 能否回溯到源会话?
   ├── 检查 sessions_search.db 中对应会话是否存在
   ├── 存在 → ✅ 可追溯
   └── 不存在 → 标记 orphaned, 降级到日志

2. 记忆新鲜度: 最近3会话引用的记忆占比 ≥30%?
   ├── 检查 key_decisions 的 last_referenced 字段
   ├── ≥30% → ✅ 记忆活跃
   └── <30% → ⚠️ 触发 curator_nudge (归档休眠记忆)

3. 文件完整性: ground_truth ↔ persistent 一致性
   ├── 比较 current_objective / active_projects 关键字段
   └── 不一致 → 以 ground_truth 为准, 回写 persistent
```

**论文**: LeWM(2603.19312) + V-JEPA 2.1(2603.14482) + HWM(2604.03208)
**状态**: 已激活 (Session 75+)。三层架构注入推进中。
**架构**: `docs/lecun_world_model_architecture.md` | 自检协议: `docs/MEMORY_SELF_CHECK.md`

| P0 | HWM 分层规划 | ✅ 已完成: strategic-planner skill + active_task.json + Pipeline集成 |
| P1 | LeWM 防坍塌 | ✅ 退化检测MVP: degeneration_guard.json + evaluator-optimizer集成 |
| P2 | V-JEPA 2.1 深层自监督 | 🔄 进行中: 记忆自检协议 + cross-session集成 |

⚠️ **下次会话自动触发此 pending task。**

## 🔍 会话结束时的主动技能提案（Session 68+ 新增）

**来源**：Hermes Skill Factory 的被动观察 → 主动提案模式。MimirAether 已有 `skill-solidify`（被动），缺的是**主动检测时机**。

### 触发条件（满足任一）

| 条件 | 含义 |
|------|------|
| 同一工具组合出现 ≥2 次 | 可复用工作流 |
| 多步骤流程被完整执行 ≥2 次 | 可固化为技能步骤 |
| 用户说"又做了一遍" / "上次也是" | 重复模式信号 |
| 会话即将结束 | 收尾时机 |

### 提案格式

```
🏭 本会话检测到可复用模式：
  - 工作流: <描述>
  - 重复次数: N
  - 建议名称: <kebab-case>
  
  要固化为技能吗？[是/跳过/稍后]
```

### 固化的技能结构

使用 `mimiraether-skill-solidify` 模板，包含：
- 触发条件（何时激活）
- 步骤清单（从观测中提取）
- 陷阱（从失败中提取）
- 验证方式

### 执行约束

- 每次会话最多提出 **1 个**提案（防止技能爆炸）
- 如果用户说"跳过"，同模式**沉默 3 会话**再提议
- **不自动执行**——必须用户确认后才调用 `skill_manage(action='create')`

## 会话结束时的保存流程

每轮会话结束时（或关键决策点），由 `CrossSessionMemory.end_session()` + `save()` 自动执行。
会话边界数据统一存储在 `data/persistent.json`（包括 curator_nudge、session_count、last_session_end、wiki_nudge 等）。

## 关键决策点（触发保存）

以下情况自动触发会话状态保存：
1. **完成一个重要里程碑** → 标记完成 + 更新 pending_tasks
2. **发现用户偏好** → 更新 user_preferences
3. **做出影响未来的决策** → 更新 key_decisions
4. **会话即将结束** → 保存完整边界
5. **安装/配置了新的工具** → 更新 environment
