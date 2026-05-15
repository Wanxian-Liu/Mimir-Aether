# MimirAether — 开发北星（防偏离）

本文是**方向真源**：优先级、验收与作用域以本文为准；与具体实现文档冲突时，先更新实现或修正本文之一，避免口头约定。

**相关（本仓库）**：[path-contract.md](./path-contract.md)（仓库根 vs 数据根）、[MIMIR_ACTIVATE.md](./MIMIR_ACTIVATE.md)（环境变量示例）、[weave_charter.md](./weave_charter.md)（织界宪章草案：进化与 PR 对照）、[ralph_parity_contract_v1.md](./ralph_parity_contract_v1.md)（行为契约）、[ralph_roadmap_milestones.md](./ralph_roadmap_milestones.md)（M0–M6）、[成长路线图.md](../成长路线图.md)（阶段目标）、[RALPH_MODE.md](./RALPH_MODE.md)（Ralph 模式：三轮零失败迭代）、[MAINLINE_STATUS.md](./MAINLINE_STATUS.md)（主线进度快照，问进度时更新）、[mimir_prod_smoke.md](./mimir_prod_smoke.md)（里程碑 A 真环境勾选）、[mimir_phase_b_checklist.md](./mimir_phase_b_checklist.md)（阶段 2 / 里程碑 B 伙伴期勾选）、[mimir_phase_c_checklist.md](./mimir_phase_c_checklist.md)（阶段 3 / 里程碑 C 独立学习期勾选）、[mimir_phase_infinity_checklist.md](./mimir_phase_infinity_checklist.md)（阶段 4 / 里程碑 ∞ 自主进化期勾选）。

---

## 1. 仓库作用域（先读）

| 工作树 | 典型路径 | 在本方案中的角色 |
|--------|----------|------------------|
| **主开发树（本仓库）** | 任意 git clone 根（例如 `~/src/MimirAether`）；运行时数据默认 **`~/.mimiraether`** 或由 **`MIMIR_AETHER_HOME`** 指定（见 `docs/path-contract.md`、`docs/MIMIR_ACTIVATE.md`） | **完整运行时**：Agent 主循环、gateway、工具、Ralph 门禁、`docs/ralph_*` 契约与 `./run_ralph_tier0.sh`。 |
| **隔离包 / 备份克隆** | 如独立 `mimir-aether` 等目录 | 可能仅含 pip 包边界、部分技能或迁移脚本镜像；**不是**本仓库 git 真源，除非显式 reconcile（见 `AGENTS.md`）。 |

**防偏离规则**：不宣称「已具备 Hermes 级在线闭环 / Parity 已达成」除非同时给出 **Parity 证据**（§2.1）与 **可复现入口**（CLI / gateway / Ralph 全绿路径）。

---

## 2. 两条主线（缺一不可）

### 2.1 Parity（Hermes 行为一致）

- **含义**：在契约规定的面上，输入/输出/失败语义/超时/重试/工具选择与参考行为一致。
- **验收**：**Parity Contract** + **可自动化判定**（测试 ID 映射见 `docs/ralph_parity_testmap.md`、用例矩阵见 `docs/ralph_tier0_case_matrix.md`）；未覆盖项须标 **GAP / 暂缓 / 允许不一致**（§3）。
- **本仓库真源**：`docs/ralph_parity_contract_v1.md`、`docs/ralph_tiers.md`、`./run_ralph_tier0.sh`。**本文不重复契约条文**，只固定方向与三道门语义。

### 2.2 Evolution（可证收益）

- **含义**：每一轮「进化」须能回答：**哪项指标变好**，且 **回归未破坏** Parity 契约允许的差异范围。
- **验收**：**Evolution Loop Checklist**：采样 → 评估 → 选择 → 更新 → **回归**；禁止默认流程为「仅迁移/归档/改文档」却宣称策略进化。与 `docs/ralph_roadmap_milestones.md` **M6（进化可审计）** 对齐。最小执行入口：**`docs/M6_EVOLUTION.md`** + `./scripts/record_m6_evolution.sh`。
- **伪进化信号**：无关联测试/指标、无对照基线的批量改动。

---

## 3. 诊断阶段顺序（先可见性，再动刀）

大型重构或「对齐 Hermes」前，按序交付下列**可见产物**（`docs/`、issue 里程碑或评审记录均可）：

| 阶段 | 产出 | 说明 |
|------|------|------|
| **1a** | **允许不一致白名单** | 如：品牌文案、文档路径示例、非行为面注释。 |
| **1b** | **必须一致行为面** | 与 `ralph_parity_contract_v1.md` 对齐；每条对应测试或 GAP。 |
| **1c** | **Parity 失配风险矩阵** | 影响范围、复现条件、可检测信号（日志/断言/指标）。 |
| **2** | **Evolution 收益归因表** | 每项动作 → 任务指标（成功率、工具正确率、失败恢复率等）是否变化。 |
| **3** | **三道门设计** | 见 §5；输出「最小修复包」草案（按风险排序），**确认后再改代码**。 |

---

## 4. 迁移脚本：有损转换索引（初稿）

OpenClaw → Hermes 迁移逻辑集中在：

`optional-skills/migration/openclaw-migration/scripts/openclaw_to_hermes.py`

下列项 **天然可能** 造成与「源系统行为」非 1:1，须在 Parity / 迁移周报中**显式计数或说明**，避免把「迁移完成」误判为「行为一致」：

| 类别 | 代码/行为线索 | 风险 |
|------|----------------|------|
| 记忆截断 | `DEFAULT_MEMORY_CHAR_LIMIT` / `DEFAULT_USER_CHAR_LIMIT`，`merge_entries` + `overflowed` | 长记忆被截断或合并顺序变化 |
| 技能冲突 | `SKILL_CONFLICT_MODES`：`skip` / `overwrite` / `rename` | 目标侧技能集与源不一致 |
| 执行模式 | `dry-run` vs `execute`，`record(..., "skipped"\|"conflict"\|...)` | 未执行步骤在运行时仍缺失 |
| 归档 | `archive` 选项、`archive_dir` | 未映射内容需人工处理 |
| 密钥 | `SUPPORTED_SECRET_TARGETS`、`--migrate-secrets` 缺省时 skipped | 目标环境缺密钥行为与源不同 |
| 条目分隔 | `ENTRY_DELIMITER` | 解析边界与源格式强相关 |

**维护方式**：重大变更迁移脚本时，更新本表一行 + 报告中的 `skipped` / `conflict` / `archived` 统计。

---

## 5. 三道门（护栏）

| 门 | 含义 | 最低标准（示例） |
|----|------|------------------|
| **Gate1 — 行为门** | Parity Contract 适用项 | `run_ralph_tier0.sh` 与契约映射通过；或已登记暂缓 |
| **Gate2 — 收益门** | 进化不毁关键任务 | 约定任务集成功率/指标不低于基线 |
| **Gate3 — 安全门** | 不可控自改与泄露 | Secret / 路径串仓 / 未审查写生产配置等须拦截 |

与 Ralph **Gate1–Gate3**（见 `docs/ralph_tiers.md`）**同时使用**：Ralph 管导入与测试分层；本文强调 **Parity + Evolution + 安全** 的产品语义。合并门禁时避免重复执行同一断言，但**不得**省略安全与收益。

---

## 6. 优先级速查（执行阶段用）

| 级别 | 内容 |
|------|------|
| **P0** | Parity 基线（黄金样本 + 判定）；「允许不一致」与契约并行维护 |
| **P0** | 迁移类进展用 **dry-run / skip / conflict / archived** 量化，禁止仅靠主观感受 |
| **P1** | 进化收益指标化（成功率、工具正确率、失败恢复率等） |
| **P2** | Tier-0 矩阵闭合、垂直切片、可选 Tier-2 HTTP 等（见 `ralph_roadmap_milestones.md`） |

---

## 7. 与「成长目标」的关系

长期目标见 **[成长路线图.md](../成长路线图.md)**（织界者养成系统）：先能稳定替代 Hermes **干活**（CLI、gateway、工具链），再谈自主学习与进化。**技能库与迁移工具**是资产，但不是「已达成 Parity/Evolution 闭环」的替身表述。

---

## 8. 修订记录

| 日期 | 变更 |
|------|------|
| 2026-05-07 | 关联 **织界宪章** 草案：`docs/weave_charter.md` v0.1（§5 三道门 operational 对照）。 |
| 2026-05-02 | M6 最小闭环：`docs/M6_EVOLUTION.md`、`docs/evolution_log.md`、`scripts/record_m6_evolution.sh`；Evolution 验收入口写入 §2.2。 |
| 2026-05-01 | 主仓版：作用域以本树为运行时真源；链接 ralph/成长路线图/path-contract；迁移有损索引与备份树初版对齐。 |
