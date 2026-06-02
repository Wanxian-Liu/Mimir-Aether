# IQ-42: Cursor backlog 建议表

> **状态**：建议表（供 Cursor 额度恢复后参考）  
> **来源**：IQ #17 Phase1 执行中发现的余债 + 未做项

## P0: IQ-31/32/33/34 — **已合 main**（`a0dc323` · 2026-06-01）

| ID | 状态 | 说明 |
|----|:----:|------|
| **IQ-31～34** | ✅ | 代码在 `main`；HANDOFF 在 `docs/mimir-handoff/IQ-31/`～`34/` |
| **下一拍** | — | **TASK_QUEUE §13 MW-00** 验收 + 刘哥开 `MIMIR_WM_PREDICTOR=1`（见 `mw-00-prod-env.md`） |

~~勿再开「+105 行」实现 PR。~~

## P1: WM-B5 LLM 预测器 — **不做（已裁定）**

| ID | 状态 | 真源 |
|----|:----:|------|
| **WM-B5** | **DEFERRED** | [`docs/phase0/wm-b5-llm-predictor-deferred.md`](../phase0/wm-b5-llm-predictor-deferred.md) |

**刘哥 2026-05-19**：非原先目标功能；边际意义不大 → **保持现状**。禁止 `MIMIR_WM_LLM_PREDICTOR` / `llm_predictor.py`。  
**若要 WM 出数据**：开步骤 1～4 env + **规则** `MIMIR_WM_PREDICTOR=1`（IQ-31），见 §13 **MW-00**。

## P2: 设计稿待实现

| ID | 文件 | 行数 | 风险 | 依赖 | 说明 |
|----|------|:----:|:----:|:----:|------|
| **IQ-40** | `agent/agent_loop.py` | ~+25 | 🟡 | P1 合入 | 每 N 轮 nudge（`MIMIR_NUDGE_INTERVAL`） |
| **IQ-41** | `agent/parallel_dispatcher.py` + `agent/agent_loop.py` | ~+160 | 🟡 | 无 | 并行工具执行（`MIMIR_PARALLEL_TOOLS=1`） |

**建议**：Cursor 实现前先确认刘哥是否想要，或等 IQ-45 收官后作为 Horizon 下一阶段。

## P3: 观察/运维 → **并入 §14 IQ-55**

| ID | 说明 | 真源 |
|----|------|------|
| **IQ55-02/03** | search audit + brain_metrics 周快照 | [`MIMIR_IQ55_ROADMAP.md`](../MIMIR_IQ55_ROADMAP.md) |
| **IQ55-OPS-04** | 7d WM/intent closeout | `iq55-ops-closeout.md`（待写） |
| **SELF-LOOP** | 每周周报 | §10 |

## P0/P1/P2（Mimir 自检 → IQ-55 粒）

见 **§14**：IQ55-10（搜索≤40%）· IQ55-11（进化 applied）· IQ55-12（延迟画像）· IQ55-20～24 · IQ55-30～60 backlog。

## 不做

| ID | 原因 |
|----|------|
| WM B2 RECALL | IQ-12 BLOCK（WM-Q2=每步问我+B1<3d） |
| IQ-14 飞书冒烟 | 依赖刘哥飞书发话 |
| EV-VISION | 刘哥 DEFER |
| CLR-B-FEISHU | Owner 刘哥 |
