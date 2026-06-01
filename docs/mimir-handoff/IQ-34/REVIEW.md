# IQ-34 复核要点

1. **三粒联合回归风险**：IQ-31/32/33 独立验证通过后才合到一起测 tier0
2. **env 门控不冲突**：`MIMIR_WM_PREDICTOR`（IQ-31）和 `MIMIR_INTENT_PREDICTOR`（IQ-32）是两个独立 env，互不影响
3. **agent_loop.py 注入位置**：在 nudge message 组装之后、首轮 LLM 调用之前；搜索 `# Nudge messages` 或 `nudge_messages` 标签确定位置
4. **M6 记录**：改 `agent/` 后需 `./scripts/record_m6_evolution.sh "IQ-31/32/33: WM B4 + intent fallback + 契约测"`

## 已知不做

- B5 LLM 预测器（需独立拍板）
- F 并行工具（P2 设计）
- E 对话内 nudge（P2 设计）
- SESSION_SEARCH_BACKEND 生产默认改
