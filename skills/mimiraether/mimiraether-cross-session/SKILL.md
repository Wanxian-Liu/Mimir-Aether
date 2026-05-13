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

## 会话结束时的保存流程

每轮会话结束时（或关键决策点），由 `CrossSessionMemory.end_session()` + `save()` 自动执行。
会话边界数据统一存储在 `data/persistent.json`（包括 curator_nudge、session_count、last_session_end 等）。

## 关键决策点（触发保存）

以下情况自动触发会话状态保存：
1. **完成一个重要里程碑** → 标记完成 + 更新 pending_tasks
2. **发现用户偏好** → 更新 user_preferences
3. **做出影响未来的决策** → 更新 key_decisions
4. **会话即将结束** → 保存完整边界
5. **安装/配置了新的工具** → 更新 environment
