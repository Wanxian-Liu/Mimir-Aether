# Wave 7 — Gate C/D + 智商 5.5 · Cursor 新窗执行手册

> **给刘哥**：每个灰框 = **新开一个 Cursor 对话**，整段粘贴。严格按 **§39 → §40 → … → §50** 顺序，**一次一粒**。  
> **给 Agent**：Read 本页 **§0** + 对应 **§N** + [`p2-long-iqevo-wave7-gate-cd-plan.md`](../../phase0/p2-long-iqevo-wave7-gate-cd-plan.md)；`verification-before-completion` 后再标 `[x]`。

**Goal：** 完成进化门禁 **档位 C/D** + rubric **≥5.5**（或 documented exception）。

**真源：** [`iqevo-evolution-gates.md`](../../phase0/iqevo-evolution-gates.md) · [`p2-long-iqevo-wave7-gate-cd-plan.md`](../../phase0/p2-long-iqevo-wave7-gate-cd-plan.md)

**Tech Stack：** Python 3.12 · `MIMIR_AETHER_HOME=~/.mimiraether` · 仓库 `~/src/MimirAether/`

**Out of scope：** 提交 `data/persistent.json` · Hermes 全量对比研究 · 无界自改参

---

## §0 主上下文（每个新窗先读）

```text
仓库：~/src/MimirAether
运行时：MIMIR_AETHER_HOME=~/.mimiraether
计划：docs/phase0/p2-long-iqevo-wave7-gate-cd-plan.md
门禁：docs/phase0/iqevo-evolution-gates.md（档位 C/D）
方向：docs/MIMIR_IQ_EVOLUTION_DIRECTION.md（现 4.8/10，目标 5.5）
协作：docs/MIMIR_LIU_CURSOR_BRIDGE.md
backlog：docs/MIMIR_EXEC_BACKLOG.md §15 Wave 7

硬约束：
- §40 完成前：不要在生产依赖 AUTO_EVOLVE 真效果（可保持 env=1 但无写入不算过 §41）
- §46 刘哥签字前：禁止 Unified Plan 1c 代码（§47–§49）
- 1c 禁止：写 SKILL.md、替代 Top-3 AutoTuner、无界改 degeneration_guard 源文件
- 每粒：./run_ralph_tier0.sh 全绿（sandbox 外跑若 flaky）；触达 agent|gateway|tools → record_m6_evolution.sh
- surgical diff only

Superpowers：executing-plans → 单粒 → verification-before-completion → backlog [x] + gates 表 + bridge §4
```

---

## §39 · DOC-01（文档对齐 · 可选首粒）

```text
【DOC-01 · 新窗执行】

Read §0 主上下文。

任务：过时段对齐（纯文档）
- docs/MIMIR_EXEC_BACKLOG.md：进化门禁行改为「A/B [x] · 当前 Wave 7」；补 §15 Wave 7 表指向 plan
- docs/MIMIR_LIU_CURSOR_BRIDGE.md §1：档位 C/D 保留 [ ]；删/改「仍关 staging AUTO_EVOLVE」「下一档 B」；§5 进度笔记 tier0/Gateway 一行刷新
- docs/phase0/iqevo-evolution-gates.md：C/D 表加「执行：wave7 plan」链
- docs/MAINLINE_STATUS.md：最近更新 2026-05-26；Wave 6 + Gate B + Wave 7 进行中一句

验证：rg "下一档 B" docs/ 应为 0；无需 tier0

完成：DOC-01 [x]；bridge §4 一行。
```

---

## §40 · IQ-EVO-40（analysis → evolution 时序 · 阻塞）

```text
【IQ-EVO-40 · 新窗执行】

Read §0 + docs/phase0/p2-long-iqevo-wave7-gate-cd-plan.md §5。

任务：修 post_close_analysis 与 AUTO_EVOLVE 的时序
- 读 agent/agent_loop.py _close_pipeline、agent/post_close_analysis.py、agent/execution_pipeline.py schedule_post_close_evolution
- 目标：MIMIR_AUTO_ANALYSIS=1 且 MIMIR_AUTO_EVOLVE=1 时，有 errors/degraded 的 close → LLM analysis → fix suggestion → SKILL 写入（默认 get_skills_dir()）
- 实现方案在 plan §5 A/B 二选一；优先 A（analysis worker 末尾触发 evolution）

验证：
1. pytest tests/agent/test_evolution_loop_integration.py -q（扩展或新增 async 路径）
2. cd ~/src/MimirAether && ./run_ralph_tier0.sh
3. 本地：MIMIR_AUTO_ANALYSIS=1 MIMIR_AUTO_EVOLVE=1 跑最小 close 脚本，确认 skill 文件变更

完成：IQ-EVO-40 [x]；record_m6_evolution.sh；bridge §4 一行（含测试名）。
```

---

## §41 · IQ-EVO-41（staging 真实 SKILL 写入）

```text
【IQ-EVO-41 · 新窗执行】

Read §0。前置：IQ-EVO-40 [x]。

任务：staging 真实写入证据（非 gate-b-pilot 目录）
- 确认 ~/.mimiraether/.env：MIMIR_AUTO_ANALYSIS=1、MIMIR_AUTO_EVOLVE=1
- 制造 1 次带 degraded_tools 或 errors 的真实 close（可：飞书让 Mimir 跑 mimir_ops/故意坏工具；或受控脚本走 agent_loop close，须写清 session 非 pilot）
- 证据：docs/phase0/iqevo-gate-c-staging-write-evidence.md
  - skill 路径、改前/改后摘要、对应 analysis_artifacts 路径
  - 声明：非 data/ops/gate-b-pilot/

验证：ls -l 目标 SKILL.md mtime；artifact 存在

完成：IQ-EVO-41 [x]；请 Mimir bridge §4 确认（可选）；bridge §4 Cursor 一行。
```

---

## §42 · IQ-EVO-42（Gate C 结案）

```text
【IQ-EVO-42 · 新窗执行】

Read §0 + iqevo-evolution-gates.md 档位 C。前置：IQ-EVO-41 [x]。

任务：Gate C1–C3
- C1：B 已 [x]
- C2：MIMIR_AETHER_HOME=~/.mimiraether 连续 3 次 ./scripts/run_evolution_eval.sh，记录 3 个 compare JSON 路径
- C3：审查 skills/ 改动；MIMIR_ISSUES 无技能改坏 P0
- 写 docs/phase0/iqevo-gate-c-closeout.md
- 更新 iqevo-evolution-gates.md C 行 [x]
- ./scripts/restart_gateway_hard.sh；/health ok

验证：3× eval exit 0；tier0 1× 绿（本粒）

完成：IQ-EVO-42 [x]；bridge §1 档位 C → [x]；§4 一行。
```

---

## §43 · GATE-D1（1c Spike）

```text
【GATE-D1 · 新窗执行】

Read §0 + MIMIR_UNIFIED_PLAN.md 冲突3 子阶段1c。前置：无（可与 §42 并行，但 §47 仍等 §46）。

任务：1 页 Spike
- 产出：docs/phase0/decision-ring-compressor-1c-spike.md
- 含：DecisionRing 可学参数面 · Compressor 可学参数面 · 数据输入（feedback/tune/artifact）· 风险 · 模块 touch 表

验证：文件存在且 ≤2 页等价

完成：GATE-D1 [x]；bridge §4 一行。
```

---

## §44 · GATE-D2（1c 与 1b 分界）

```text
【GATE-D2 · 新窗执行】

Read §0 + wave7 plan §7。前置：GATE-D1 [x]。

任务：在 spike 文档增「边界」节或 docs/phase0/iqevo-1c-boundary.md
- 明文：1c 不写 SKILL · 不替代 Top-3 tuned_thresholds 键 · 与 AUTO_EVOLVE 分工

完成：GATE-D2 [x]；bridge §4 一行。
```

---

## §45 · GATE-D3（contract 草案 ≥5 条）

```text
【GATE-D3 · 新窗执行】

Read §0。前置：GATE-D2 [x]。

任务：≥5 条拟新增 tier0 contract（可先写清单，§49 再实现 pytest）
- 产出：docs/phase0/iqevo-1c-contract-draft.md
- 每条：ID · 断言一句话 · 对应未来 test 文件/函数名

完成：GATE-D3 [x]；bridge §4 一行。
```

---

## §46 · GATE-D4（刘哥签字 · 人工）

```text
【GATE-D4 · 刘哥操作 — 非 Cursor 工程粒】

前置：GATE-D1～D3 [x]。

刘哥在 docs/MIMIR_LIU_CURSOR_BRIDGE.md §1 增加一行（模板）：

### 2026-05-26 — 刘哥拍板：授权 Unified Plan 1c 实现（Gate D）

已读 `decision-ring-compressor-1c-spike.md` + `iqevo-1c-boundary.md` + contract 草案。
授权 Cursor 执行 IQ-EVO-43～45（1c 有界实现）。仍禁止写 SKILL / 替代 Top-3。

Mimir：bridge §4 签收「Gate D4 已签字」即可，勿改 agent 代码除非 §47 起。
```

---

## §47 · IQ-EVO-43（1c DecisionRing 有界）

```text
【IQ-EVO-43 · 新窗执行】

Read §0 + spike + boundary。前置：§46 已签字（bridge §1 有 D4 行）。

任务：DecisionRing 有界策略学习（最小可工作）
- 仅改 agent/decision_ring.py 及必要接线；有界 clamp；可审计
- 对照 iqevo-1c-contract-draft 实现至少 2 条 contract

验证：pytest 相关 + ./run_ralph_tier0.sh

完成：IQ-EVO-43 [x]；record_m6_evolution.sh；bridge §4。
```

---

## §48 · IQ-EVO-44（1c Compressor 有界）

```text
【IQ-EVO-44 · 新窗执行】

Read §0。前置：IQ-EVO-43 [x]。

任务：Compressor 有界自适应（与 1b Top-3 正交）
- touch context_compressor / core_loop 构造路径
- 有界、可关（env 门控可选）

验证：tier0 + contract

完成：IQ-EVO-44 [x]；record_m6_evolution.sh；bridge §4。
```

---

## §49 · IQ-EVO-45（1c contract 落地 + 草案 closeout）

```text
【IQ-EVO-45 · 新窗执行】

Read §0。前置：IQ-EVO-44 [x]。

任务：
- tests/contract/test_horizon_iqevo_wave7_1c.py（manifest 纳入 tier0）
- docs/phase0/p2-long-iqevo-wave7-1c-closeout.md（工程结案，非整 Wave）
- iqevo-evolution-gates.md D1–D3 标 [x]（D4 依 bridge 签字）

验证：./run_ralph_tier0.sh 3 连绿（本粒或 Wave 7 末粒）

完成：IQ-EVO-45 [x]；bridge §4。
```

---

## §50 · IQ-EVO-46（rubric 复评 #6 + Wave 7 closeout）

```text
【IQ-EVO-46 · 新窗执行】

Read §0。前置：IQ-EVO-42 [x]；IQ-EVO-45 [x]（1c 若跳过须 bridge 记录 defer 1c）。

任务：
- 更新 docs/phase0/iq-scoring-rubric.md（复评 #6）
- 更新 docs/MIMIR_IQ_EVOLUTION_DIRECTION.md §1.1
- 写 docs/phase0/p2-long-iqevo-wave7-closeout.md
- 目标 ≥5.5；否则 documented exception + 差多少 + 是否启动 §51

验证：加权计算写入 rubric；tier0 1×

完成：IQ-EVO-46 [x]；Mimir bridge §4 复评一行；整波 Wave 7 表全 [x]。
```

---

## §51 · IQ-EVO-47（可选 · Intent 生产 MVP）

```text
【IQ-EVO-47 · 仅当 §50 <5.5 且 #8 为主瓶颈】

Read §0 + IQ-EVO-32 离线 MVP。

任务：最小生产 Intent 路径（非全量 Predictor）— 范围在 plan 内另定，须刘哥确认后做。

默认：跳过，在 Wave 7 closeout 记「§51 deferred」。
```

---

## 进度检查清单（刘哥）

| 顺序 | § | ID | 你做什么 |
|:--:|:--:|-----|----------|
| 0 | §0 | — | 每窗粘贴 |
| 1 | §39 | DOC-01 | 可选 |
| 2 | §40 | IQ-EVO-40 | **必做** |
| 3 | §41 | IQ-EVO-41 | 可让 Mimir 协助真实 close |
| 4 | §42 | IQ-EVO-42 | Gate C |
| 5–7 | §43–45 | GATE-D1～D3 | 文档 |
| 8 | §46 | GATE-D4 | **你签字** |
| 9–11 | §47–49 | IQ-EVO-43～45 | 1c 代码 |
| 12 | §50 | IQ-EVO-46 | 智商结案 |
| 13 | §51 | IQ-EVO-47 | 按需 |
