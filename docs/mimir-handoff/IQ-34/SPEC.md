# IQ-34 实现指引

## 合并顺序

**推荐**：IQ-32 → IQ-33 → IQ-31（从最独立到最依赖 runtime）

| 步骤 | 文件 | 来源 |
|------|------|------|
| 1 | `agent/intent_predictor.py` | IQ-32 SPEC.md |
| 2 | `tests/agent/test_intent_predictor.py` | IQ-32 SPEC.md |
| 3 | `tests/agent/test_iq33_non_redundant_nudges.py` | IQ-33 SPEC.md |
| 4 | `agent/agent_loop.py` | IQ-31 SPEC.md |
| 5 | tier0 验证 | 见下方 |

## 改动汇总

| 文件 | 改动 | 行 | 来源 |
|------|------|:--:|:----:|
| `agent/intent_predictor.py` | `build_intent_context_block` 加低置信分支 | +5 | IQ-32 |
| `agent/agent_loop.py` | import + context_snapshot + predict 调用 + 渲染 | +20 | IQ-31 |
| `tests/agent/test_intent_predictor.py` | 4 tests（高置信/低置信/端到端/disabled） | +40 | IQ-32 |
| `tests/agent/test_iq33_non_redundant_nudges.py` | 4 tests（去重契约） | +40 | IQ-33 |
| **合计** | **4 文件，无删除** | **~+105** | — |

## 注意点

- 所有改动都是 **env 门控**：`MIMIR_WM_PREDICTOR`（默认 0）和 `MIMIR_INTENT_PREDICTOR`（默认 1）
- `agent/world_model_spike.py` **不改** — 只用其已有的 `predict` / `is_wm_predictor_enabled`
- `agent/core_loop.py` **不改**
- 测试文件各自独立，可单独跑

## 特别提醒

IQ-31 的 `world_model_spike.predict` 注入是 **建议而非强制**。实现时注意：
- 注入的 `<wm-prediction>` tag 应在 cross-session context 末尾（system prompt 段）
- 不覆盖、不合并 `<intent-context>`（来自 intent_predictor）
- 两者共存时互不冲突
