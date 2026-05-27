# HERM-CUR-02 · skill_curator 生命周期闭环

**Date:** 2026-05-27  
**Wave:** 10 · Horizon C §19.1  
**tier0:** 见验收运行计数（+lifecycle + contract 测）

## 交付

| 项 | 结果 |
|----|------|
| `scan_all_skills()` | 扫描 repo `skills/` + `$MIMIR_AETHER_HOME/skills` + `external_dirs` |
| `run_lifecycle_pass()` | 写 `skill_usage` 初值、生成 ≤2KB markdown 报告、log |
| 合并建议 | `curator_actions()` 嵌入 lifecycle 报告 |
| archived 约定 | 既有 `skills/.dormant/` + `dormant_skills` registry |
| 周期钩子 | `MIMIR_SKILL_CURATOR_ON_CLOSE=1` → `agent_loop._close_pipeline` 后台线程 |

## Env

| 变量 | 默认 | 说明 |
|------|------|------|
| `MIMIR_SKILL_CURATOR_ON_CLOSE` | **关** | `1` 时每次 pipeline close 触发 `run_lifecycle_pass` |

## 测试

- `tests/agent/test_skill_curator_lifecycle.py`
- `tests/contract/test_horizon_herm_cur_02.py`

## 已知限制

- 多根目录同名 skill：先发现者优先。
- 胶囊化/归档仍人工或 `capsulize_and_dormant`；lifecycle pass 不自动移动目录。

## Next

- **HERM-TGR-02** tool cache metrics
- **HERM-SDH-02** subdirectory hints in system prompt
