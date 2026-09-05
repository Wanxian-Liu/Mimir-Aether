---
name: delegate-subagent
description: 委托任务给AI子代理并收集结果。管理从任务创建到委托再到结果聚合的完整生命周期。**执行层**：真实实现为 tools/delegate_tool.py（delegate_task 工具）+ agent/delegate_subagent.py（SubagentManager）。编排层见 dispatching-parallel-agents。
version: 2.0.0
category: productivity
tags: [delegation, subagent, 任务委托, 子代理, 并行, execution-layer]
auto_load: false
metadata:
  related_skills: [dispatching-parallel-agents, subagent-driven-development]
  复活记录: 2026-09-05 从 .dormant 复活（v1.1 规划稿 → v2.0 对齐真实实现）
---

# delegate-subagent v2.0 — MimirAether 子代理派发

> **v2.0 复活说明（2026-09-05）**：v1.1 是 7 月早期规划稿（标注"模块待实现"），8 月技能策展误归档 dormant。此后真实实现已落地：`tools/delegate_tool.py`（1203 行，delegate_task 工具）+ `agent/delegate_subagent.py`（SubagentManager）。v2.0 对齐真实实现重写。诊断见 `wiki/discussions/2026-09-05-四方讨论-Mimir子代理派发能力复活.md`。

## 真实实现（真源，勿凭旧稿想象）

| 组件 | 路径 | 作用 |
|------|------|------|
| **delegate_task 工具** | `~/src/MimirAether/tools/delegate_tool.py`（L682 `def delegate_task`，L1059 schema） | 主入口：spawn 子代理（隔离上下文/独立终端/受限工具集），父代理阻塞至完成，仅收最终摘要 |
| **SubagentManager** | `~/src/MimirAether/agent/delegate_subagent.py`（Task CRUD + CLI） | 任务状态管理（~/.mimiraether/tasks/），用于需要持久任务追踪的场景 |
| **路由接线** | `gateway/router/core_route_mixin.py` | 确保 delegate_task 作为内置工具路由，不当作自由文本转发给 LLM |
| **gateway 注册** | `tools/delegate_tool.py` L1189 `name="delegate_task"` | 工具注册点（MCP-style handler） |

## delegate_task API（对齐 L682 签名）

```python
delegate_task(
    goal: str | None = None,          # 单任务模式：子代理目标（自包含，它不知道你的对话历史）
    context: str | None = None,       # 子代理需要的全部背景：文件路径/报错/约束
    toolsets: list[str] | None = None, # 子代理工具集（默认继承父级；可限制）
    tasks: list[dict] | None = None,  # 批量并行模式：[{goal, context, toolsets}, ...] 最多 3 个并发
    max_iterations: int | None = None, # 每子代理最大工具轮数（默认取 config.yaml delegation.max_iterations）
    acp_command: str | None = None,   # ACP 子代理覆盖（如 'claude'），默认继承父 transport
    acp_args: list[str] | None = None, # ACP 参数（默认 ['--acp', '--stdio']）
    parent_agent=None,                # 运行时注入（不能手动传）
) -> str  # JSON: {"results": [{...}], ...} 每任务一条
```

## 两种模式

1. **单任务**：给 `goal`（+context/toolsets）→ 派 1 个子代理
2. **批量并行**：给 `tasks` 数组（≤3 项）→ 全部并发，一起返回。**要并行就把所有 delegate_task 放同一响应**（一次响应内多次调用 = 并行；分开 = 串行）

## 何时该派（default-delegate policy —— schema 内嵌，务必遵守）

**用 delegate_task 当：**
- 可分解为 ≥2 个独立子任务的任务
- ≥3 个同模式任务（独立、同 pattern）
- 子任务相互无依赖（可并行）
- 子任务各 ≥30s 且 I/O 重
- 推理重子任务（debug / code review / research synthesis）
- 会淹没你上下文的任务（中间数据只进子代理，你只见最终摘要）
- 需要并行独立工作流（A 和 B 同时调研）

**不用 delegate_task（用别的）：**
- 单步小操作 / 总量 <60s → 直接做
- 强依赖链（子任务不独立）→ 自己做
- 无推理的机械多步 → execute_code
- 单个工具调用 → 直接调工具
- 需要用户交互 → 子代理不能用 clarify

## 子代理的硬限制（子代理不可调用）

`delegate_task`（禁止递归，MAX_DEPTH 硬顶）、`clarify`、`memory`、`send_message`、`execute_code`

## 配置（config.yaml delegation 段）

```yaml
delegation:
  max_iterations: 50        # 子代理默认迭代上限（防死循环/22 步失控）
  provider: ...             # 可选：子代理专用 provider/model
  model: ...
```

- 未配置 provider → 子代理继承父级凭据
- 并发上限 `_get_max_concurrent_children()`（默认 3）

## 子代理 prompt 结构（高质量派发的关键）

子代理对你的会话**零记忆**——所有上下文必须进 prompt。好 prompt 三要素：

1. **聚焦** — 一个清晰问题域（"修 agent-tool-abort.test.ts 的 3 个失败" ✅ / "把测试修好" ❌）
2. **自包含** — 理解问题所需的全部信息都在 context 里（文件路径、错误消息、项目结构、约束）
3. **明确产出** — 返回什么（根因 + 改动摘要 / PASS 或差距清单）

### 调试类模板

```python
delegate_task(
    goal=f"Fix the {N} failing tests in {file_path}",
    context=f"""Test failures:
{error_messages}

1. 读测试文件理解每个测试验证什么
2. 定位根因（禁止绕过症状——找真因）
3. 修复并跑测试验证
Return: 根因 + 改动摘要。""",
    toolsets=["terminal", "file"]
)
```

### 研究类模板

```python
delegate_task(
    goal=f"Research {topic} and extract actionable findings",
    context=f"""Scope: {scope}
Focus: {focus_list}
1. 搜索/读资料
2. 提取模式、代码示例、关键洞见
3. 映射到我们的架构
Return: 结构化发现。""",
    toolsets=["web", "file"]
)
```

## 编排层配合

| 技能 | 关系 | 状态 |
|------|------|------|
| `dispatching-parallel-agents` | 并行派发决策流（何时并行/何时不） | **active** |
| `subagent-driven-development` | 每任务派新子代理 + 两阶段评审（spec → quality） | dormant（待四方定去留） |

## Pitfalls（真实实现教训）

- **死子代理**：无法继续的子代理（被问题卡住）= 死锁。设合理 max_iterations（默认 50，简单任务调低）
- **冲突修复**：两个子代理改同一文件 = merge hell。派发前确认域真正独立
- **上下文遗漏**：最常见的失败——假设子代理"知道"会话前文。所有上下文都进 prompt
- **躲在子代理后面**：2 个工具能自己做完的别派——子代理有成本（上下文/token/延迟），用于真并行，不用于日常工具调用
- **父代理心跳冻结**：delegate_task 期间父 `_last_activity_ts` 冻结——长任务需 heartbeat（实现内已处理 L486-510，无需干预）

## 验证复活是否落地

```bash
# 1. 工具注册
grep -n "name=\"delegate_task\"" ~/src/MimirAether/tools/delegate_tool.py
# 2. 技能文件存在（两侧）
ls ~/.mimiraether/skills/mimiraether/delegate-subagent/SKILL.md
ls ~/src/MimirAether/skills/mimiraether/delegate-subagent/SKILL.md
# 3. dormant 无残留
find ~/.mimiraether/skills/.dormant -iname "*delegate-subagent*"
find ~/src/MimirAether/skills/.dormant -iname "*delegate-subagent*"
# 4. 本会话工具列表可见 delegate_task（系统提示含其 schema）
```
