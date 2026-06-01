# MW-00: IQ-31/32/33/34 验收报告

> **日期**：2026-06-02 · **作者**：MimirAether
> **git commit**：`a0dc323`（Cursor 合入）

## 1. 合入确认

```bash
git merge-base --is-ancestor a0dc323 HEAD  # → ✅
```

`a0dc323` 是当前 `main` 的祖先，确认已合入。

## 2. 代码改动验证

### WM 预测器（IQ-31）— `agent/agent_loop.py`

```
58:  from .world_model_spike import is_wm_predictor_enabled, predict as wm_predict
288: # WM predictor: advisory context (env MIMIR_WM_PREDICTOR, default off)
289: if turn == 0 and is_wm_predictor_enabled():
292:     _wm_pred = wm_predict(
```

✅ import + inject 块均存在，turn 0 触发，env 门控。

### Intent fallback（IQ-32）— `agent/intent_predictor.py`

```bash
grep -c 'confidence\|_LOW_CONFIDENCE\|< 0.5' agent/intent_predictor.py
```

✅ 低置信度分支已合入。

### 契约测试（IQ-33）

| 文件 | 结果 |
|------|:----:|
| `tests/agent/test_iq33_non_redundant_nudges.py` | **4 passed** ✅ |
| `tests/agent/test_intent_predictor.py` | **9 passed** ✅ |

合计 **13 tests / 13 passed**。

## 3. 验收结论

| 条件 | 状态 |
|:----|:----:|
| `a0dc323` 在 main | ✅ |
| `wm_predict` 注入 agent_loop.py | ✅ |
| IQ-33 契约测试 4/4 | ✅ |
| Intent predictor 测试 9/9 | ✅ |
| 不可修改代码（除非 tier0 回归） | ✅ 未触碰 |

**MW-00 验收通过** ✅

## 4. 下一步

刘哥需执行 `mw-00-prod-env.md` 中的 env 设置，开启 `MIMIR_WM_PREDICTOR=1` 后重启 gateway。
