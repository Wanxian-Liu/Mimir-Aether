# IQ-42: Cursor backlog 建议表

> **状态**：建议表（供 Cursor 额度恢复后参考）  
> **来源**：IQ #17 Phase1 执行中发现的余债 + 未做项

## P0: IQ-31/32/33/34 — **已合 main**（`a0dc323` · 2026-06-01）

| ID | 状态 | 说明 |
|----|:----:|------|
| **IQ-31～34** | ✅ | 代码在 `main`；HANDOFF 在 `docs/mimir-handoff/IQ-31/`～`34/` |
| **下一拍** | — | **TASK_QUEUE §13 MW-00** 验收 + 刘哥开 `MIMIR_WM_PREDICTOR=1`（见 `mw-00-prod-env.md`） |

~~勿再开「+105 行」实现 PR。~~

## P1: WM B5（需刘哥拍板）

| ID | 文件 | 行数 | 风险 | 依赖 | 说明 |
|----|------|:----:|:----:|:----:|------|
| **WM-B5** | `agent/world_model_spike.py` + `agent/llm_predictor.py` | ~+200 | 🔴 | WM-Q5 拍板 | LLM 级预测器，成本需控制 |

**当前**：刘哥未拍板，不实现。

## P2: 设计稿待实现

| ID | 文件 | 行数 | 风险 | 依赖 | 说明 |
|----|------|:----:|:----:|:----:|------|
| **IQ-40** | `agent/agent_loop.py` | ~+25 | 🟡 | P1 合入 | 每 N 轮 nudge（`MIMIR_NUDGE_INTERVAL`） |
| **IQ-41** | `agent/parallel_dispatcher.py` + `agent/agent_loop.py` | ~+160 | 🟡 | 无 | 并行工具执行（`MIMIR_PARALLEL_TOOLS=1`） |

**建议**：Cursor 实现前先确认刘哥是否想要，或等 IQ-45 收官后作为 Horizon 下一阶段。

## P3: 观察/运维

| ID | 说明 | 价值 |
|----|------|:----:|
| **IQ-M1** | 7d skill_view 计数（IQ-25 已加） | IQ-M1 证据 |
| **IQ-M2** | search_first_audit 复跑 | IQ-M2 证据 |
| **SELF-LOOP** | 每周周报（§10 唯一 `[ ]`） | 自律 |

## 不做

| ID | 原因 |
|----|------|
| WM B2 RECALL | IQ-12 BLOCK（WM-Q2=每步问我+B1<3d） |
| IQ-14 飞书冒烟 | 依赖刘哥飞书发话 |
| EV-VISION | 刘哥 DEFER |
| CLR-B-FEISHU | Owner 刘哥 |
