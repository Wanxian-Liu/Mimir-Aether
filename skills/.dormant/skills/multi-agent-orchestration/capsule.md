# [DORMANT] multi-agent-orchestration

**沉寂时间**: 2026-11-22T02:34:57.955105+00:00
**原始分类**: skills
**描述**: Anthropic multi-agent research 实战——orchestrator-worker 模式（委派/提示原则/评估/上下文）。设计多 agent 系统/改进四方协作/Mimir 委派能力时用。
**触发阈值**: 60天未触碰

---

## 技能要点

# Multi-Agent Orchestration（Anthropic 实战——orchestrator-worker）

> **来源**：Anthropic《How we built our multi-agent research system》（2025-06——全文在 `~/wiki/raw/agent-architecture/B3-*`）
> **核心**：orchestrator-worker 模式——lead agent 规划+委派——subagent 并行研究——结果综合

## 为什么多 agent（实证）

- **token 使用解释 80% 性能方差**（BrowseComp 评估）——多 agent = 分布式扩展 token 预算
- **多 agent 系统比单 agent 强 90.2%**（研究评估——Opus 4 lead + Sonnet 4 subagents）
- **但烧 token**：agent 用 ~4x 聊天 token——多 agent 用 ~15x——**必须高价值任务才值**

## Orchestrator-worker 架构

```
用户查询 → Lead agent（分析/制定策略）
  ├── spawn subagent 1（并行探索方向 A——独立上下文）
  ├── spawn subagent 2（并行探索方向 B）
  └── spawn subagent 3（并行探索方向 C）
  → 各 subagent 压缩结果返回 lead → lead 综合最终答案
```

- **动态多步搜索**（vs 静态 RAG）：subagent 迭代搜索——适应新发现——分析结果
- **搜索=压缩**：subagent 独立上下文并行压缩——只把重要 token 传回 lead

## 六条提示原则（我们可直接用）

1. **像 agent 一样思考**：模拟 agent 环境看它逐步工作——发现失败模式（过度搜索/啰嗦查询/选错工具）
2. **教 orchestrator 委派**：每个 subagent 需要——目标+输出格式+工具/来源指导+清晰边界——**否则重复工作/漏缺口**（实证：3 个 subagent 重复查同一供应链）
3. **努力程度匹配查询复杂度**（scale effort to query complexity）：
   - 简单事实 → 1 agent 3-10 工具调用
   - 直接对比 → 2-4 subagent 各 10-15 调用
   - 复杂研究 → 10+ subagent 明确分工
   - **防过度投资简单查询**（早期失败模式）
4. **工具设计关键**：agent-工具接口 = 人-计算机接口——工具描述要清晰/独立用途——坏描述带 agent 走错路——**工具测试 agent：测工具→重写描述→40% 任务时间下降**
5. **让 agent 自我改进**：给 prompt+失败模式→agent 诊断→改进（Claude 4 是好 prompt 工程师）
6. **先宽后窄**（start wide then narrow）：短宽查询探路→再钻细节（防过特定查询零结果）

## 附录技巧（长任务/评估）

- **终态评估**：改状态的 agent 任务——评估最终状态而非逐步过程（承认多路径）
- **长会话管理**：完成阶段摘要存外部记忆→新阶段干净上下文→检索续接（防上下文溢出）
- **子 agent 输出落盘**（防"传话游戏"）：subagent 直接写文件系统→lead 拿轻量引用——**防大输出经对话历史复制（token 税）**

## 与我们系统对照

- 四方协作 = orchestrator-worker（Hermes=lead——OpenClaw/Loki/Mimir=workers）——**原则 2/3 直接可用**（委派要目标+边界+努力分级）
- **Mimir 的 PI 问题 = 原则 3 没落地**（est 启发式简单——应"努力程度匹配复杂度"——简单任务 1 agent——复杂才 delegate）
- **subagent 输出落盘** = 我们的"落盘协议"（四方段直接写卡）——实证正确
- **长会话管理** = Mimir 压缩（150K）+ 摘要写回方向

## 反模式
- ❌ 简单查询 spawn 50 subagent（过度投资——努力不匹配）
- ❌ 委派无边界（重复工作/漏缺口）
- ❌ subagent 输出全走 lead 转述（传话游戏——token 税）
- ❌ 上下文溢出硬扛（不摘要/不落盘）

---

> 此胶囊由 Skill Curator 自动生成。原始技能已移入 .dormant/。
> 调用 `skill_view("multi-agent-orchestration")` 即可自动唤醒。
