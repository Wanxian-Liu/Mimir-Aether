# [DORMANT] delegate-subagent

**沉寂时间**: 2026-11-04T14:15:54.191778+00:00
**原始分类**: mimiraether
**描述**: 委托任务给AI子代理并收集结果。管理从任务创建到委托再到结果聚合的完整生命周期。**执行层**：真实实现为 tools/delegate_tool.py（delegate_task 工具）+ agent/delegate_subagent.py（SubagentManager）。编排层见 dispatching-parallel-agents。
**触发阈值**: 60天未触碰

---

## 技能要点

# delegate-subagent v2.0 — MimirAether 子代理派发

> **v2.0 复活说明（2026-09-05）**：v1.1 是 7 月早期规划稿（标注"模块待实现"），8 月技能策展误归档 dormant。此后真实实现已落地：`tools/delegate_tool.py`（1203 行，delegate_task 工具）+ `agent/delegate_subagent.py`（SubagentManager）。v2.0 对齐真实实现重写。诊断见 `wiki/discussions/2026-09-05-四方讨论-Mimir子代理派发能力复活.md`。

## 坑：子代理会越权写盘 / 提交到共享仓（2026-10-11 实证）

- **实证**：派两席做**只读**外部调研（clone 在 `~/.mimiraether/tmp/`），prompt 明写「不要写任何文件到 `~/wiki` 或 `~/src`」，**两席仍各自写了取证件并 `git commit` 进 `~/wiki`（3 个 commit）**。
- ⇒ **委托后必查**：`cd <共享仓> && git log --oneline -5 | cat && git status --porcelain`；发现越权产物就按「单一真源 / 不另建卡」归置：内容并入正卡 → 文件移出仓（副本留 `~/.mimiraether/tmp/...`）→ 补 commit。
- ⇒ prompt 里写「只读」**不等于**隔离。要隔离就**不给 file 写面**（只发 terminal+search、且要求把中间产物写到指定 tmp 目录）。
- ⇒ 子代理给的 `路径:行号` cite **必须自己复跑至少一条**再签字（本轮复跑：2 处「复算数字」与实测不符——`grep -c` 计的是**出现次数**，别按「文件数」直觉填）。

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
    parent_agent=None,         

... (truncated)

---

> 此胶囊由 Skill Curator 自动生成。原始技能已移入 .dormant/。
> 调用 `skill_view("delegate-subagent")` 即可自动唤醒。
