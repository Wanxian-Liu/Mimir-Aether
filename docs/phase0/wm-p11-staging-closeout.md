# WM-P11-OPS · Staging 验收 + replan prompt 接线（2026-06-01）

> **轨**：IQ 5.5 Phase2 · Track 3a/3b  
> **前提**：WB-B00～B03 · WM-P11-00～04 已结案（[`wm-phase11-closeout.md`](./wm-phase11-closeout.md)）

## 3a Staging 验收

| 项 | 结果 |
|----|------|
| `MIMIR_WM_VOE_LEARNING=1` | surprise → JSONL **1 行** + `learned_surprises.json` 有 key |
| `MIMIR_WM_VOE_RECALL=1` | 同 `(expected,actual)` 第二次 **clean** + `surprise_suppressed` |
| `MIMIR_WM_VOE_REPLAN_CTX=1` | 首次 surprise 生成 `wm_learning_context` |

隔离验收（`MIMIR_AETHER_HOME` 临时目录 · 2026-06-01）：

```
r1 surprise_detected
r2 clean True
jsonl_lines 1
learned_keys ['operation success|operation failed']
```

生产 **`.env` 仍默认 0**；staging 开三项后再 `ensure_single_gateway.sh` 重启。

## 3b Gateway / agent prompt 接线

| 项 | 状态 |
|----|:----:|
| `set_pending_wm_learning_context` | [`agent/wm_voe_learning.py`](../../agent/wm_voe_learning.py) |
| surprise → queue | [`agent/degeneration_guard.py`](../../agent/degeneration_guard.py) |
| 消费一次进 system prompt | [`agent/callers_mixin.py`](../../agent/callers_mixin.py) `_build_full_messages` · `<wm-voe-learning>` |
| 单测 | [`tests/agent/test_wm_prompt_injection_p11_ops.py`](../../tests/agent/test_wm_prompt_injection_p11_ops.py) |
| tier0 | **674 PASS** |

## 刻意未做

- Phase 1.2 分层规划
- 生产默认开启 WM 三开关
- 与 IQ-IDX / IQ-MEM 混 PR

## Staging 入口（Mimir）

```bash
export MIMIR_AETHER_HOME=~/.mimiraether
export MIMIR_WM_VOE_LEARNING=1
export MIMIR_WM_VOE_RECALL=1
export MIMIR_WM_VOE_REPLAN_CTX=1
# scripts/ensure_single_gateway.sh && 退化场景或 pytest tests/agent/test_wm_voe_learning_p11.py
```
