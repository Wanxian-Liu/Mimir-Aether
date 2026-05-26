# IQ-EVO-03：AUTO_ANALYSIS 启用提案

> **提案轨 A** — Mimir 分析 + 建议，刘哥拍板，Cursor 工程实现  
> **父任务**：§15 IQ-EVO-03  
> **日期**：2026-05-25

---

## 1. 现状：代码已就位，但门闩没插

### 1.1 已建成的组件（全部存在且有测试）

| 组件 | 路径 | 功能 |
|------|------|------|
| `PostExecutionAnalyzer` | `agent/post_analysis.py` (206行) | LLM 分析执行轨迹 → 生成 EvolutionSuggestion |
| `SkillEvolutionPipeline` | `agent/skill_evolution.py` (587行) | 接收 suggestion → FIX/DERIVED/CAPTURED → 写 SKILL.md |
| `ToolQualityManager` | `agent/tool_quality.py` | 跟踪工具成功率、标记退化 |
| `ExecutionRecorder` | `agent/execution_recorder.py` | 录制完整执行轨迹 |
| `close_execution_pipeline` | `agent/execution_pipeline.py:114` | 汇总 errors/quality/degraded_tools |
| `schedule_post_close_evolution` | `agent/execution_pipeline.py:264` | `MIMIR_AUTO_EVOLVE=1` 时自动应用 suggestion |
| `build_analysis_from_pipeline` | `agent/execution_pipeline.py:151` | 从 pipeline 结果构建 LLM 分析 prompt |
| `apply_analysis_to_pipeline` | `agent/execution_pipeline.py:170` | 解析 LLM 分析结果 → 写入 quality manager |
| JEPA 自修引擎 | `agent/jepa_session_hook.py` | 会话结束自修（独立通路） |

### 1.2 但 LLM 分析这一步从未运行

`agent/agent_loop.py:392-408`（`_close_pipeline`）当前的调用链：

```
close_execution_pipeline()          ← 总是跑，产出 errors/quality/degraded
schedule_post_close_evolution()     ← 只在 MIMIR_AUTO_EVOLVE=1 时跑
schedule_post_close_jepa_cycle()    ← 独立门控
```

**缺失的一环**：`build_analysis_from_pipeline` → LLM 调用 → `apply_analysis_to_pipeline` 这条通路没有接入 agent_loop。

`MIMIR_AUTO_ANALYSIS=1` 在 `post_analysis.py:4` 和 `skill_evolution.py:4` 都有文档注释，但**代码里没有任何地方检查这个环境变量**。

### 1.3 当前能跑什么 vs 不能跑什么

| 通路 | 状态 | 门控 |
|------|------|------|
| 工具质量追踪（ToolQualityManager） | ✅ 生产运行 | 始终开 |
| 执行录制（ExecutionRecorder） | ✅ 生产运行 | 始终开 |
| pipeline 结果汇总（errors/degraded_tools） | ✅ 生产运行 | 始终开 |
| **LLM 分析执行轨迹 → 生成 EvolutionSuggestion** | ❌ 未接入 | **`MIMIR_AUTO_ANALYSIS=1`（待实现）** |
| 根据 suggestion 自动改技能 | ⚠️ 代码有但依赖上一步的 suggestion | `MIMIR_AUTO_EVOLVE=1` |
| JEPA 自修 | ⚠️ 偶尔 no_candidates | 独立门控 |

---

## 2. 建议：分两步走，先开分析，后开进化

### Step 1 — 接上线（本周可做）

在 `agent_loop.py` 的 `_close_pipeline` 中，当 `MIMIR_AUTO_ANALYSIS=1` 时，调用 `build_analysis_from_pipeline` 构建 prompt → 用 agent 自身的 LLM 能力做一次分析 → `apply_analysis_to_pipeline` 写结果。

**伪代码**（改动位置：`agent/agent_loop.py:392-408`）：

```python
def _close_pipeline(self, task_name: str = "") -> None:
    try:
        from agent.execution_pipeline import (
            close_execution_pipeline,
            schedule_post_close_evolution,
            build_analysis_from_pipeline,
            apply_analysis_to_pipeline,
        )
        from agent.jepa_session_hook import schedule_post_close_jepa_cycle

        result = close_execution_pipeline(
            task_name=task_name or self.task_id,
            session_id=self.task_id,
        )

        # ── NEW: LLM analysis gate ──
        if os.environ.get("MIMIR_AUTO_ANALYSIS", "").strip() in ("1", "true", "yes"):
            if result.get("errors") or result.get("degraded_tools"):
                prompt = build_analysis_from_pipeline(result, task_name)
                if prompt:
                    # reuse agent's LLM for analysis (fire-and-forget in background)
                    _schedule_analysis_task(self, prompt, result, task_name)

        schedule_post_close_evolution(result)
        schedule_post_close_jepa_cycle(result, session_id=self.task_id)
    except Exception:
        pass
```

**改动量估计**：`agent_loop.py` ~15 行 + 一个 background task wrapper ~30 行。零新依赖。

### Step 2 — 观察 1-2 周后再决定是否开 AUTO_EVOLVE

Step 1 只是**生成 suggestion 并存盘**，不会自动改任何技能文件。观察：
- Agent 每轮延迟（LLM 分析是 fire-and-forget，不阻塞）
- Suggestion 质量（人工抽查 analysis_artifacts 目录）
- 有没有幻觉 suggestion（target 指向不存在的工具/技能）

确认 suggestion 质量稳定后，再评估是否开 `MIMIR_AUTO_EVOLVE=1`（自动应用 suggestion 到技能文件）。

---

## 3. 风险与对策

| 风险 | 概率 | 影响 | 对策 |
|------|------|------|------|
| LLM 分析增加延迟 | 低 | 中 | fire-and-forget 后台任务，不阻塞 Agent 回复 |
| 幻觉 suggestion（建议改不存在的工具） | 中 | 低 | Step 1 只存不执行；人工抽查 1-2 周 |
| LLM 分析消耗 token | 确定 | 中 | 每次分析 ~5-10K tokens（prompt + 轨迹 + 分析），每次会话一次 |
| 轨迹太长超出 prompt 窗口 | 低 | 低 | `post_analysis.py:131` 已有截断（head 25K + tail 25K） |
| 与 JEPA 冲突（两个自修通路） | 低 | 中 | 两条通路独立；JEPA 是代码级自修，AUTO_ANALYSIS 是技能级建议，不冲突 |

### Token 成本估算

| 场景 | 每次 cost |
|------|-----------|
| 简单任务（无 error, 短轨迹） | ~$0.01-0.03（DeepSeek） |
| 复杂任务（有 error, 长轨迹） | ~$0.05-0.10 |
| 不触发条件（无 error 且无 degraded tools） | $0（跳过） |

---

## 4. 需要先确认的前置问题

### 4.1 Agent 能否在 finally 块里调自己的 LLM？

`_close_pipeline` 在 agent loop 的 `finally` 块里。如果把 LLM 分析放在主路径上，会**阻塞消息回复**。必须做成 `asyncio.create_task` fire-and-forget。

但这里有个架构问题：agent loop 是同步还是异步的？需要 Cursor 确认 `_close_pipeline` 的调用上下文。

### 4.2 `MIMIR_AUTO_ANALYSIS` 在哪设？

| 方式 | 优点 | 缺点 |
|------|------|------|
| `~/.mimiraether/.env` | 简单 | Gateway 需重启 |
| Gateway 环境变量 | 可热切换 | 需要改 gateway 代码 |
| 运行时 feature flag | 最灵活 | 需要新机制 |

**建议**：先用 `.env` 方式，对齐现有 `MIMIR_AUTO_EVOLVE` 的约定。

### 4.3 元问题：这个功能你想要吗？

当前 IQ=3.8 的核心瓶颈是「没有形成可测的进化闭环」（方向文档 §1.1）。开 AUTO_ANALYSIS 是**最小的进环第一步**——先产生 suggestion，再决定是否自动应用。

但也可以用更简单的方式起步：先不开，等 20-query 基准（IQ-EVO-01）和飞书实测（IQ-EVO-02）做完，有了记忆检索的基线数字后，再决定要不要加 LLM 分析这一层。

---

## 5. 建议决策

| 选项 | 描述 |
|------|------|
| **A** | 立刻做 Step 1（~50 行代码，Cursor 工程），开观察 |
| **B** | 先做 IQ-EVO-01/02（记忆基线→飞书实测），AUTO_ANALYSIS 排后面 |
| **C** | 搁置，等 Horizon 拍板后再统一排 |

**Mimir 建议**：**B**。先拿 IQ-EVO-01 的 20-query 基准数字——这是进化闭环的「before」照片。没有 before，after 就没意义。AUTO_ANALYSIS 是「after」的其中一步，等 before 到手了再决定要不要做、做多少。

---

## 6. 修订记录

| 日期 | 摘要 |
|------|------|
| 2026-05-25 | 初版：现状审计、两步方案、风险、建议 |
