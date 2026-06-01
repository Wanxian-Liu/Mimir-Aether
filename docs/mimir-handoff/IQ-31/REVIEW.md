# IQ-31 复核要点

1. **函数导入正确**：`from .world_model_spike import predict as wm_predict, is_wm_predictor_enabled` — 函数名确认无误
2. **注入位置正确**：在首轮 LLM 调用之前、nudge message 组装之后；不影响已有 nudge 逻辑
3. **env 门控生效**：`MIMIR_WM_PREDICTOR != 1` 时 predict 不走
4. **异常安全**：任何 `predict()` 抛异常都不应阻塞 conversation（try/except logger.warning）
5. **上下文不污染**：即使 prediction 异常，cross-session context 也不留残缺 key
6. **不重复**：preemptive search + recall 已满足时，predictor 不应重复注入相同建议

## 已知未做

- **B5 LLM 预测器**：本粒只接线规则预测器，LLM 级是 WM 步骤 5，需独立拍板
- **predict 对已有 cross-session context 的去重**：preemptive search 与 predictor 可能都建议「recall -> session_search」；契约测见 IQ-33
