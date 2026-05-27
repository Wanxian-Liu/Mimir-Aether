# IQ-EVO-47 — Intent 生产 MVP closeout

**Date:** 2026-05-27  
**Grain:** IQ-EVO-47 / Wave 7 §51  
**tier0:** `tests/agent/test_intent_predictor.py` + `tests/contract/test_horizon_iqevo_wave7_intent.py`

---

## 范围（最小生产路径）

| 项 | 实现 |
|----|------|
| 模块 | `agent/intent_predictor.py` — `IntentPrediction` + 规则 `predict()` |
| 生产接线 | `core_loop.run_conversation` 每轮预测 + log |
| Prompt | `_build_full_messages` 注入 `<intent-context>` |
| 路由 | `config_mixin._resolve_api_config` — `block_cheap_route` 时跳过 smart cheap 模型 |
| 离线 | **不变** — `scripts/label_intent_offline.py`（IQ-EVO-32） |

**非范围：** 训练分类器、全量 Hermes IntentPredictor、默认改模型矩阵。

---

## 开关

| Env | 默认 | 含义 |
|-----|------|------|
| `MIMIR_INTENT_PREDICTOR` | **1**（开） | 关：`0` / `false` / `no` |

---

## 验证

```bash
python3 -m pytest tests/agent/test_intent_predictor.py tests/contract/test_horizon_iqevo_wave7_intent.py -q
./run_ralph_tier0.sh
```

**Gateway 重启** 后飞书一轮；log 应有 `[IntentPredictor] intent=… complexity=…`。

---

## Rubric #8

| 前 | 后（诚实） |
|----|------------|
| 3.5 — 无生产 Predictor | **4.0** — 规则 MVP 已接线；非 ML 分类器 |

见 [`iq-scoring-rubric.md`](./iq-scoring-rubric.md) Wave 7 复评表。
