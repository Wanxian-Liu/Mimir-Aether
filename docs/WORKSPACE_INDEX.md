# MimirAether 工作区全局索引

> **最后由 Mimir 更新**: 2026-05-21  
> **用途**: 一次性了解所有工作线在哪、什么状态、下一步是什么

---

## 一、活跃工作线

| # | 工作线 | 主文档 | 状态 | 下一步 |
|---|--------|--------|:--:|------|
| 1 | **路线B 物理世界模型** | `skills/mimiraether_physics_reasoner/` | ✅ 6颗粒全完成 全深研 | 候选G融合 |
| 2 | **路线A 物理求解器** | 同上 `solver.py` | ⚠️ 只做EV-PHY01 | 决策：继续或关停 |
| 3 | **候选K self_evolution** | `agent/self_evolution/` | ✅ 代码建成 3🔴已修 | 接agent loop |
| 4 | **候选C LLM+WM桥接** | `skills/mimiraether_physics_reasoner/llm_wm_bridge.py` | ✅ 6场景 | — |
| 5 | **Mimicore提炼** | `docs/MIMICORE_EXTRACTION_PLAN.md` | 📋 10粒全未执行 | 等Cursor |
| 6 | **三方案融合** | `docs/MIMIR_UNIFIED_PLAN.md` | ✅ 评估完成 | 等Cursor §3 |
| 7 | **模块依赖拓扑** | `docs/MODULE_DEPENDENCY_TOPOLOGY.md` | ✅ | — |
| 8 | **全局融合设计** | `docs/WM_MIMIR_FUSION_PLAN_FINAL.md` | ✅ | — |

---

## 二、外部依赖

| 依赖 | 状态 | 阻塞什么 |
|------|:--:|------|
| Cursor Bridge §3 | 🔴 0回复 | 三方案工程刀 + AC架构刀 + Mimicore提炼 |
| 琬弦架构产出 | 🔴 未到 | 架构方案落地 |

---

## 三、代码资产

### 物理世界模型引擎

| 文件 | 行数 | 颗粒 |
|------|:--:|:--:|
| `world_model_engine.py` | 533 | 0/1/2/4 |
| `cost_module.py` | 313 | 3 |
| `planner.py` | 374 | 5 |
| `llm_wm_bridge.py` | 294 | 候选C |
| **∑** | **1514** | — |

### self_evolution 引擎

| 文件 | 行数 | 审查 |
|------|:--:|:--:|
| `__init__.py` | 61 | ✅ |
| `state_encoder.py` | 265 | ✅ v1v2 |
| `cost.py` | 169 | ✅ v1v2 |
| `planner.py` | 159 | ✅ v1v2 |
| `memory.py` | 172 | ✅ v1v2 |
| `engine.py` | 357 | ✅ v1v2 |
| **∑** | **1183** | — |

---

## 四、审查报告索引

| 颗粒 | 审查文档 | 版本 | Bug |
|:--:|------|:--:|:--:|
| 0 | `baseline_analysis_v3.md` | v3 | 0 |
| 1 | `integrator_deep_study_v3.md` | v3 | 2 (已修) |
| 2 | `pbd_review_v3.md` | v4 | 0 |
| 3 | `cost_review_v3.md` | v3 | 0 |
| 4 | `grain4_review_v3.md` | v4 | 2 (F1+F2已修) |
| 5 | `grain5_review_v3.md` | v4 | 2 (V1+V2已修) |
| K | `self_evolution_review_v1v2.md` | v1v2 | 3 (已修) |

---

## 五、关键文档速查

| 想了解 | 看这个 |
|--------|--------|
| 整体路线图 | `docs/MIMIR_UNIFIED_PLAN.md` |
| 所有任务backlog | `docs/MIMIR_EXEC_BACKLOG.md` |
| 主线状态 | `docs/MAINLINE_STATUS.md` |
| 刘哥-Cursor约定 | `docs/MIMIR_LIU_CURSOR_BRIDGE.md` |
| 物理世界模型方案 | `docs/MIMIR_PHYSICS_WORLD_MODEL_PLAN.md` |
| 物理方案重读对比 | `docs/MIMIR_PHYSICS_PLAN_REREAD_COMPARISON.md` |
| Mimicore提炼方案 | `docs/MIMICORE_EXTRACTION_PLAN.md` |
| 模块依赖拓扑 | `docs/MODULE_DEPENDENCY_TOPOLOGY.md` |
| WM×Mimir融合设计 | `docs/WM_MIMIR_FUSION_PLAN_FINAL.md` |
| IR-20260520事故 | `docs/MIMIR_INCIDENT_IR-20260520.md` |
| 架构审计(agent核心) | `docs/ARCHITECTURE_AUDIT_AGENT_CORE.md` |
| 智商审计(硬编码) | `docs/IQ_AUDIT_HARDCODED_THRESHOLDS.md` |
| GOD文件清单 | `docs/GOD_FILE_INVENTORY.md` |
| 演进日志 | `docs/evolution_log.md` |
| 交付审计清单 | `docs/MIMIR_MONTHLY_AUDIT_CHECKLIST.md` |
| 开发北极星 | `docs/DEVELOPMENT_NORTH_STAR.md` |

---

## 六、文档清理状态

| 文档 | 状态 |
|------|:--:|
| `WM_MIMIR_FUSION_PLAN_V1.md` | 📦 已合并到FINAL，可删除 |
| `WM_MIMIR_FUSION_PLAN_V2.md` | 📦 已合并到FINAL，可删除 |
| `WM_MIMIR_FUSION_V1V2_COMPARISON.md` | 📦 已合并到FINAL，可删除 |

---

## 七、快速链接

- **tier0**: `./run_ralph_tier0.sh` (181+2 PASS)
- **物理引擎测试**: `skills/mimiraether_physics_reasoner/test_*.py`
- **self_evolution测试**: `agent/self_evolution/test_*.py`
- **Git分支**: `main` (主线) / `feat/self_evolution_jepa` (候选K)
