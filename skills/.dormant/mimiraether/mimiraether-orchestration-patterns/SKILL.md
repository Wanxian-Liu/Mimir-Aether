---
name: mimiraether-orchestration-patterns
description: MimirAether多代理编排设计模式 — 提取自Hermes Kanban系统的通用架构原则：任务分解、Fan-out/Fan-in、依赖门控、反诱惑规则、Handoff数据合约、重试诊断。独立于Kanban基础设施，适用于任何多代理协作场景。
version: 1.0.0
metadata:
  mimiraether:
    tags: [orchestration, multi-agent, patterns, architecture, decomposition]
    related_skills: [subagent-driven-development, mimiraether-plan-mode, delegate-subagent]
    derived_from: hermes-agent kanban-orchestrator + kanban-worker (v2026.5.7)
    derivation_date: 2026-05-12
    derivation_notes: "提取通用设计模式，去Kanban API依赖；推理依据→delegate_task/subagent-driven-development"
---

# MimirAether 多代理编排模式

> 提取自 Hermes Kanban 系统的通用架构原则。这些模式**独立于具体基础设施**——无论你是用 `delegate_task`、子代理、终端进程还是手动分工，同样的原则适用。

## 何时编排 vs 直接执行

创建多代理编排当满足以下任一条件：

1. **需要多个专长者** — 研究 + 分析 + 实现需要不同思维模式
2. **工作应跨崩溃/重启存活** — 长时间运行、周期性、重要任务
3. **用户可能中途介入** — 任意步骤都可能需要human-in-the-loop
4. **多个子任务可并行** — Fan-out 加速
5. **预期有审核/迭代** — 审核者循环在工作输出上迭代
6. **审计轨迹有价值** — 需要追溯"谁做了什么"

如果 **以上都不适用** — 只是一次性小推理任务 — 直接回答或用一个 `delegate_task` 即可。

---

## 核心模式

### 模式1: 分解Playbook

```
用户请求 → 提取独立工作流 → 映射到专长 → 绘制依赖图 → 执行
```

**步骤：**

1. **理解目标** — 目标模糊时先澄清。澄清很便宜；派错代理很贵。
2. **分解泳道** — 提取请求中的独立工作流。不要因为措辞把不相关的事情合并。
3. **映射到能力** — 每条泳道需要什么能力？代码？研究？设计？审核？
4. **绘制依赖图** — 只链接真正有数据依赖的任务。并行可以的一定要并行。
5. **展示给用户** — 在执行前让用户确认分解方案。

**分解举例：**

- "修复阻塞并检查模型变体" → 实现任务(修复) + 探索任务(变体检查)，可并行
- "先调研文档再实现" → 调研可并行代码探索，实现等待两者产出
- "分析截图并找到相关代码" → 视觉分析(一条泳道) + 代码搜索(另一条泳道)，并行

**反模式：** 因为措辞而过度链接。以下情况不应建立依赖：
- "然后看看X" — 检查静态配置/文档，不依赖实现产出
- "还要确保Y" — 独立验证，不依赖实现产出
- "最后确认Z" — 可能是并行检查，不一定串行

### 模式2: Fan-out → Fan-in

```
         ┌── Worker A (独立任务1) ──┐
         │                         │
         ├── Worker B (独立任务2) ──┤
         │                         │
         ├── Worker C (独立任务3) ──┘
         │                         │
         └─────────────────────────→ 汇总者 (等待所有完成)
```

**关键规则：**
- **N个工作型泳道无依赖** — 全部并行启动
- **1个汇总泳道依赖所有工作泳道** — 等待所有产出后整合
- **禁止：** 把多个独立泳道打包成一个"全能"任务

**适用场景：** 调研→推荐、分析→报告、多方案探索→选优

### 模式3: 流水线 + 门控

```
规划者 → 实现者 → 审核者
  │        │        │
  └──依赖──┘──依赖──┘
```

**关键规则：**
- 每个阶段 **必须等待** 前一阶段产出
- 审核者可以 **阻断 + 反馈** → 创建新的实现任务（不重跑同一任务）
- 阻断时附上 **具体修改要求**，非"改一下"

### 模式4: 同质队列

```
Worker A: [任务1] → [任务2] → [任务3]  (序列化处理)
```

**关键规则：**
- 同一专长的N个任务无依赖 — 序列化执行
- 内存/经验在任务间累积
- 适用于单个worker负责多个同类任务

### 模式5: Human-in-the-Loop

```
Worker ── 阻断(问题) ──→ 人类 ── 解答 ──→ Worker 继续
```

**阻断写得好不好决定响应速度：**
- ❌ 差: "卡住了"
- ✅ 好: 一句话点出需要什么决定 + 深度上下文放备注

---

## 反诱惑规则（Orchestrator专用）

如果你是 **编排者** 而非 **执行者**：

1. **不要亲自执行工作** — 你的工具集被限制是有原因的
2. **任何具体任务→分配给执行者** — 无一例外
3. **不要发明不存在的Worker** — 只有确认存在的能力才能分配
4. **分解、路由、汇总** — 这就是全部职责
5. **想要"快速修复"？** — 停止。分配给正确的执行者。

---

## Handoff 数据合约

Worker完成后的产出必须结构化为下游可消费的格式：

### 代码任务 Handoff

```python
{
    "summary": "shipped rate limiter — token bucket, keys on user_id with IP fallback, 14 tests pass",
    "changed_files": ["rate_limiter.py", "tests/test_rate_limiter.py"],
    "tests_run": 14,
    "tests_passed": 14,
    "decisions": ["user_id primary, IP fallback for unauthenticated requests"],
    "artifacts": {"diff_path": "/path/to/worktree"}
}
```

### 调研任务 Handoff

```python
{
    "summary": "3 competing libraries reviewed; vLLM wins on throughput",
    "sources_read": 12,
    "recommendation": "vLLM",
    "benchmarks": {"vllm": 1.0, "sglang": 0.87, "trtllm": 0.72}
}
```

### 审核任务 Handoff

```python
{
    "summary": "reviewed PR #123; 2 blocking issues found",
    "pr_number": 123,
    "findings": [
        {"severity": "critical", "file": "api/search.py", "line": 42, "issue": "raw SQL concat"},
        {"severity": "high", "file": "api/settings.py", "issue": "missing CSRF middleware"}
    ],
    "approved": false
}
```

**合约原则：** 结构化字段让下游无需重读散文即可消费。

---

## 重试诊断

当Worker失败重试时，先读前次运行的产出：

| 前次结果 | 可能原因 | 重试策略 |
|----------|----------|----------|
| `timed_out` | 任务太重/timeout太小 | 细分任务/延长时间 |
| `crashed` | OOM或段错误 | 减小内存占用 |
| `spawn_failed` + `error` | 配置问题(凭证/路径) | 阻断求援，不盲目重试 |
| `blocked` | 前次已阻断了 | 检查阻断回复 |
| 假卡(fake cards) | Worker幻觉了未创建的任务ID | 门控应检测并拒绝 |

---

## 在MimirAether中的应用

| Hermes概念 | MimirAether等价物 |
|-------------|-------------------|
| `kanban_create` 分配任务 | `delegate_task` 或 subagent |
| 依赖图 gating | `subagent-driven-development` 2阶段审核 |
| Worker handoff | structured metadata in delegate_task result |
| Human-in-the-loop | 阻断=显式提问，不假装知道 |
| Hallucination 检测 | 验证子代理返回的实际action vs 声称的 |

**当前工具链：** `delegate_task`(子代理) + `subagent-driven-development`(SDD审核) + 直接执行(简单任务)

---

## 陷阱

- **发明不存在的专长** → Worker分配失败时静默（任务永不执行）
- **把独立泳道打包进一个任务** → 失去并行性
- **因措辞过度链接** → "还有"、"然后"、"最后"不一定意味着依赖
- **重复同一任务而非创建新任务** → 审核者反馈后应创建新的修正任务
- **完成没实际做完的任务** → 应该阻断而非伪完成
- **在依赖图形态依赖中间发现时预先创建全图** → 让汇总任务自己决定下一层怎么分解
