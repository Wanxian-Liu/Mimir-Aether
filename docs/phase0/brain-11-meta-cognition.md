# BRAIN-11: 元认知路由（skill scenario router）

> **Date**: 2026-06-02  
> **Status**: 代码已合 **main**（`9ccc1b9` · SELF-02 扩展 `aa531fc`）· 本文补 closeout  
> **Env**: `MIMIR_SKILL_ROUTE_NUDGE=1`（默认开；关：`0` / `false` / `off`）

## 实现

| 组件 | 路径 |
|------|------|
| 场景→技能推荐 | `agent/skill_scenario_router.py` |
| turn0 注入 nudge | `agent/agent_loop.py`（log：`skill-route nudge`） |
| 标记 | `[MIMIR_SKILL_ROUTE_NUDGE]` |

用户句匹配「评估/审计/自评/元认知」等场景时，首轮应出现 **skill_view**（非仅靠 auto-load 三技能）。

## 验证

```bash
pytest tests/agent/test_skill_scenario_router.py -q
```

Gateway 重启后飞书问「你进步了吗」→ `agent.log` 含 `skill-route` 且后续有 `skill_view`。

## 与 IQ-31～34 关系

WM 预测器（`MIMIR_WM_PREDICTOR`）与 skill-route **并存**；非冗余契约见 `tests/agent/test_iq33_non_redundant_nudges.py`（commit `a0dc323`）。

## 下一拍

- **BRAIN-12**：`brain_metrics_snapshot` 增 `skill_view_7d`（已合 `6397160`）  
- 生产习惯：评估类问题先 `skill_view` 再动手（SELF-06 禁止等「继续」）
