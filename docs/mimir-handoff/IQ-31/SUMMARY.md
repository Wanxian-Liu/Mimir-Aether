# IQ-31: WM B4 预测器接 agent_loop

## 做了什么

设计稿。**Cursor 实现** — 将 `world_model_spike.predict()` 注入 `agent_loop.py` 首轮，在 cross-session context 中带上 `wm_prediction` 作为**建议**。

## 为何

WM 规则预测器（Phase 0 WB-B01）已存在、有单测覆盖、但**未被任何 caller 调用**。`MIMIR_WM_PREDICTOR` env 永远为 0 的生产现状意味着 WM 预测毫无作用。

IQ-31 是 **步骤 4**（生产启用提案 wm-production-enablement.md §步骤4）—— 让预测器的 `next_context_needs` / `applicable_skills` 注入到 agent 首轮上下文，帮助 agent 更快判断意图与所需工具。刘哥拍板 WM-Q3=**批准**。

## 风险

🟡 中 — 规则预测器可能误判 intent（如 recall 关键词误触发）。但注入的是**建议而非强制**，低置信时 `next_context_needs` 为空数组。回滚：关 `MIMIR_WM_PREDICTOR` env + gateway 重启。

## 建议 commit message

```
feat: IQ-31 WM B4 预测器接 agent_loop（env 门控，默认关）
```
