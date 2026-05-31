# WM Phase 1.1 — Surprise→学习 生产化（执行计划）

> **前置**：Wave B Phase0 spike 已结案 — [`wm-phase0-spike-closeout.md`](./wm-phase0-spike-closeout.md)  
> **真源**：[`world-model-evolution-plan.md`](../proposals/world-model-evolution-plan.md) §3.1  
> **拍板**：刘哥 **另批** 后开 PR · **禁止** 与 A06.1 / Horizon C 混 PR  
> **验证标准（plan §3.1）**：同一场景**第二次** surprise 应减少或消失（需 memory recall 覆盖）

---

## Phase 1.1 与 Phase0 差距（来自 closeout）

| 目标 | Phase0 | Phase 1.1 要补 |
|------|--------|----------------|
| 学习持久化 | JSONL audit only | memory capsule 或等价可 recall 路径 |
| replan | warning only | `extra_context` 带「已记录学习」 |
| 预测 | 规则 `world_model_spike` | 可选：turn 级写入 `prediction_expected_outcome` 到 event |
| 生产 | env 默认 **0** | 门控开启策略（staging 先，非默认全开） |

---

## 工程粒（建议顺序）

| 序 | ID | 任务 | 成功标准 | 状态 |
|:--:|-----|------|----------|:----:|
| 0 | **WM-P11-00** | 钉死 1.1 范围 + 验收 | `wm-phase11-scope.md` | [x] |
| 1 | **WM-P11-01** | surprise event → memory 可 recall | 单测 + 可选 staging env | [x] |
| 2 | **WM-P11-02** | replan 注入学习上下文 | `run_checks` / replan 路径有 extra_context | [x] |
| 3 | **WM-P11-03** | 二次 surprise 回归测 | 单测或 contract：同 expected/actual 第二次不触发 | [x] |
| 4 | **WM-P11-04** | closeout + tier0 | `wm-phase11-closeout.md` | [x] |

---

## 窗口 0 · Cursor — WM-P11-00

```text
【角色】Cursor 新窗 · MimirAether · WM Phase 1.1

【前置】WB-B03 closeout [x] · 读 wm-phase0-spike-closeout.md §Phase 1.1 差距

【必读】
- docs/proposals/world-model-evolution-plan.md §3.1
- agent/wm_voe_learning.py · agent/memory_write_facade.py（写路径）
- docs/phase0/wm-phase11-execution-plan.md

【本窗】新建 docs/phase0/wm-phase11-scope.md
- In/out scope（不做 1.2 分层规划 · 不做 gateway 默认全开 · 不做 Wave A A06.1）
- 选用 memory 路径（capsule vs persistent mutator）及理由
- WM-P11-01～03 验收命令与「第二次不 surprise」操作定义
- staging 门控：MIMIR_WM_VOE_LEARNING 仍默认 0；staging 如何开

【禁止】直接改生产默认 · 混 Horizon C

【回报】scope 路径 + bridge §4：WM-P11-00 scope locked
```
