# IQ-P3-10 · 进化链失败归因（2026-06-01）

> **基线**：[`iq-p3-baseline.json`](../../.mimiraether/data/ops/iq-p3-baseline.json)（`iq_p3_evolution_ok_baseline.py`）  
> **修复**：IQ-P3-11 · `agent/skill_evolution.py` · `agent/post_close_analysis.py`

## Top-3 根因（生产 log）

| # | 现象 | 根因 | P3-11 对策 |
|---|------|------|------------|
| 1 | `post_analysis evolution failed` · `'deprecate' is not a valid EvolutionAction` | LLM 返回 `deprecate`，`EvolutionAction` 无该枚举 → **整段进化抛异常** | 新增 **`DEPRECATE`** · quality flag · **success=True** |
| 2 | `applied=1 ok=0`（真实 session_id） | **`FIX`** 目标多为 **tool 名**，`resolve_skill_dir` 找不到 → `Unsupported action for target state` | **FIX 无 skill_dir** 且有 `suggested_changes` → 降级 **`CAPTURED`** 写新 skill |
| 3 | 7d ok% **60.9%（含测试）** vs **0%（排除测试）** | tier0/契约会话 **`iq07-sess`/`iq40-sess`/`fb-sess`** 污染 `agent.log`；生产真实行几乎全 **ok=0**（#1+#2） | 基线脚本 **排除测试 session**；勿用含测试的 ok% 宣称生产肌肉 |

## 样本（节选）

```text
# 异常（修复前）
post_analysis evolution failed session_id=711aafc3-...: 'deprecate' is not a valid EvolutionAction

# 生产（修复前 · 典型）
post_analysis evolution session_id=9ee6d577-... applied=2 ok=0
post_analysis evolution session_id=7c9691192f1b7340 applied=1 ok=0
```

## P3-12 复测说明

- **历史 log 不会回溯变绿**；修复后需 **Gateway 部署 + 新 close 样本** 再跑 `iq_p3_evolution_ok_baseline.py`。
- **契约证据**：`test_skill_evolution_e009` deprecate + FIX→CAPTURED · tier0 全绿。
- **阈值**：较 P3-00 生产（排除测试）**+10pp** 或 **≥65%**（7d 窗 · ≥30 条）— 待部署后观测。

## 刻意未做

- `MIMIR_AUTO_1C_POLICY=1` 生产  
- 改 ok 日志语义为「部分成功仍记 ok=1」（保持 applied/ok 诚实计数）
