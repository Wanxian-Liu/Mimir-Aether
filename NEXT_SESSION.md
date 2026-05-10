# 下次会话启动指南

## 硬约束（必须先做）

1. **验证元规则**：收到任务后，第一件事是 `skill_view("mimiraether-tool-triggers")`
   - 检查元规则第0条是否被触发
   - 如果没触发，说明记忆断裂——需要修复跨会话机制

2. **读取持久化状态**：读 `data/persistent.json` 和 `memory/persistent.json`
   - 获取 pending_tasks 和 key_decisions
   - 确认上次会话的上下文是否恢复

## 五条药方（可选切入点）

| # | 药方 | 对应skill | 优先级 |
|---|------|-----------|--------|
| 1 | tool-triggers元规则 | mimiraether-tool-triggers | **硬约束** |
| 2 | cross-session打通 | mimiraether-cross-session | 高 |
| 3 | plan-mode实施 | mimiraether-plan-mode | 中 |
| 4 | skill固化流程 | skill_manage | 中 |
| 5 | context-compressor | mimiraether-context-compressor | 低 |

## 上次会话关键信息

- **日期**: 2025-04-18
- **事件**: 自我体检，发现五条问题，开出五条药方
- **用户**: 刘哥（rayliu）— 创造者/导师角色，给予自主权
- **核心发现**: 技能沉默是最大瓶颈 — 工具存在但不触发
- **元规则定义**: 收到任务后先加载 tool-triggers，再分析内容

## 如果记忆完全断裂

如果以上信息对你来说都是新的，说明跨会话记忆系统失效了。
请执行：
1. `skill_view("mimiraether-tool-triggers")` — 加载工具触发规则
2. `skill_view("mimiraether-cross-session")` — 修复跨会话记忆
3. 读 `data/persistent.json` — 恢复状态
