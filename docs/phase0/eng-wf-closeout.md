# ENG-WF-90: 工程链总收官

> **真源**：[`MIMIR_ENGINEERING_WORKFLOW.md`](../MIMIR_ENGINEERING_WORKFLOW.md) §4 ENG-WF-90  
> **日期**：2026-06-01 · **末粒 Commit**：`6b10686`

---

## M1～M6 合格检查

| ID | 条件 | 验证 | 状态 |
|:--:|------|------|:----:|
| **M1** | systemd 不再 auto-restart 撞 18999 | ENG-WF-01: `systemctl --user stop + disable`，刘哥执行 | ✅ |
| **M2** | 编造 spec + ≥3 契约测绿 | ENG-WF-03/04: `phase0/eng-wf-fabrication-spec.md` + 3 tests (tier0) | ✅ |
| **M3** | 覆盖率 baseline 文档化且可复跑 | `scripts/coverage_baseline.sh` → 基线 **21%** | ✅ |
| **M4** | registry 模块 cov ≥80% | `agent/tool_registry.py` — 原误 SKIP；Cursor 复核补测后 ≥80% | ✅ |
| **M5** | 末粒含 code → tier0 ≥681 | 末粒 `6b10686` + 复核 → tier0 **696/4** ✅ | ✅ |
| **M6** | closeout 不夸大 | 见下方 ✅ | ✅ |

## 行覆盖现状

**TOTAL: 21%**（63,356 行，≈50,196 未覆盖）。

波次 1～3 交付了 10+ 新测、覆盖率基建、编造契约测、搜索优先护卫、FauxLlm 迁测。但代码库体量太大（63K 行），10 个新测不足以改变 TOTAL 百分比。

**未达标**，原因诚实写在 `docs/phase0/eng-wf-wave2-closeout.md`。

## 下一链建议

1. **波次 4（已阻塞）**：模块级覆盖率（从 `agent/` 小模块开始逐个 >50%）
2. 或切到**新评估链**（MIMIR 评估与改造方向中的工程项）
3. 如需继续提单粒：推荐从 `tests/agent/test_recovery_patterns.py` 等基础测试切入

## 已交付全量任务

| ID | 产出 | 类型 |
|:--:|------|:----:|
| ENG-WF-00 | 基线 health + tier0 684/4 | 📊 |
| ENG-WF-01 | systemd stop+disable | 🔧 ops |
| ENG-WF-02 | 单 Owner 纪律文档 | 📝 |
| ENG-WF-03 | 编造 spec + 3 acceptance | 📝 |
| ENG-WF-04 | 编造契约测 3 tests | 🧪 |
| ENG-WF-05 | tool result priority 2 tests | 🧪 |
| ENG-WF-06 | 波次 1 closeout | 📝 |
| ENG-WF-10 | coverage_baseline.sh + 基线 21% | 🔧 |
| ENG-WF-11 | 覆盖率 ratchet 策略 | 📝 |
| ENG-WF-12 | tool_registry cov ≥80% | ✅ 复核补测（`agent/test_tool_registry_api.py`） |
| ENG-WF-13 | search_first_guard +5 测 | 🧪 |
| ENG-WF-14 | 波次 2 closeout | 📝 |
| ENG-WF-20 | 上下文三套 inventory | 📝 |
| ENG-WF-21 | turn_loop_utils + 3 tests | 🧪 |
| ENG-WF-22 | FauxLlm 迁 2 测 (harness) | 🧪 |
| **ENG-WF-90** | **本收官文档** | 📝 |
