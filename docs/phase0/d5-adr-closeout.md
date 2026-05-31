# D5-ADR — §6 d5 收口

> **日期**：2026-05-19（工程）· **刘哥签收** 2026-05-31  
> **ADR**：[ADR-008: Evolution canonical path](../adr/008-evolution-canonical-path.md)  
> **验证**：`./run_ralph_tier0.sh`（含 `test_d5_adr_evolution_canonical`）

## §6 d5 对照

| ID | 任务 | 状态 |
|----|------|------|
| D5-0 | Recorder 按 session 隔离 | [x] E-007 |
| D5-0b | skill 路径白名单 | [x] E-007 |
| D5-1 | 禁 `simulated:true` | [x] IEVO-01 |
| D5-2 | 单通路 FIX 写 SKILL | [x] E-009 |
| D5-3 | evolution pytest tier0 | [x] IEVO-02 |
| **D5-ADR** | 双架构 ADR 定稿 | **[x] ADR-008 · 刘哥签收 2026-05-31** |

**d5 进度**：**6/6 [x]** — §6 收口完成 · §20.3 拍板闭合。

## 路径裁定（摘要）

| 路径 | 裁定 |
|------|------|
| **A** post_close → `skill_evolution` | **生产真源** |
| **B** JEPA | 只读分析；`MIMIR_JEPA_CYCLE` 默认关 |
| **C** mimicore/evolve + 三环技能 | 泉/实验；非 Gateway 默认 |
| **D** `learn_and_evolve_8h` | 批处理研究；非 SoT |

## 代码 / 契约（最小对齐）

- `agent/skill_evolution.py` — docstring 指向 ADR-008  
- `activate_self_evolution.py` — 非 canonical 路径 warning  
- `scheduler/tasks/learn_and_evolve_8h.py` — 非 Gateway SoT 注释  
- `skills/mimiraether/mimiraether-self_evolution/__init__.py` — Path C 注释  
- `tests/contract/test_d5_adr_evolution_canonical.py`

## GitHub #21

| 项 | 状态 |
|----|------|
| D5-1 | [x] IEVO-01 |
| D5-3 | [x] IEVO-02 |
| D5-ADR | [x] ADR-008 + 本 closeout |
| 余量 | **真进化 wide 指标**、生产 ok% 提升 — 仍 **icebox** / P3-12 观测，**不**阻塞 ADR 结案 |

建议：在 #21 评论后 **close**，余量指向 §20.5 / 新 issue。

## 不在本粒

- CLR-B-FEISHU（§20.2 刘哥）  
- 生产 ok% ≥65%（P3-12 观测窗）  
- mimicore 存根填充 · ObservabilityBus 实现
