# EV-P02 — 测试命名规范审计（2026-05-24）

## 现状

真源 [`docs/TEST_NAMING_CONVENTION.md`](../TEST_NAMING_CONVENTION.md)（2026-05-21）：文件 `test_<module>_{imports,integration,edge}.py`；函数 `test_<what>_<condition>_<expected>`。EV-P02 已补 **目录双轨**、E-012、intent-action 示例及 phase0 链。

## tier0（Gate2 显式清单）

- **`agent/test_*.py`**：34 文件（~64%）— parity、M3–M5 `test_m5_*_slice`、import 烟测  
- **`tests/**/test_*.py`**：19 文件（~36%）— `tests/agent/`（E-006～E-012、intent-action、EP-C smoke）、`tests/gateway/`（E-010/E-011）  
- **Gate3**：`agent/test_tier1_e2e_agent.py`（2 cases）

**新测建议**：默认 `tests/<area>/test_<topic>.py`；仅延续 M5 切片族时放 `agent/`。

## 合规 / 偏离（抽样）

| | 路径 |
|---|------|
| ✅ 文件 | `tests/agent/test_e012_jepa_session_hook.py`、`test_agent_loop_integration.py` |
| ✅ 函数 | `test_jepa_env_on_no_candidates_skips_run_cycle`；`test_skill_path_guard_blocks_traversal`；`test_skill_evolution_fix_smoke_writes_skill_md` |
| ⚠️ 文件 | `agent/test_m5_kernel_replaceability_slice.py`（`test_m5_*` 未入规范表） |
| ⚠️ 函数 | `test_callers_mixin_model_metadata_callable`（缺 condition 段）；`test_two_stubs_satisfy_llm_invocation_port`（非三段子式） |

`tests/agent/test_e*.py`（7）：6/7 为 `test_eNNN_*` 或 `*_integration`。

## 缺口与建议

- 缺口：`test_m3_*` / `test_m5_*` 里程碑族、epic 前缀未在 2026-05-21 表内；覆盖率 ratchet 未进 Gate2。  
- Phase 0：不重命名。Phase 1 前新文件走 `tests/` + `test_e<ticket>_<slug>.py`；cov ratchet 另议。
