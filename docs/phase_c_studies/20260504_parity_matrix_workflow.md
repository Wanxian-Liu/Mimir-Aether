# 独立学习：行为矩阵与 Parity testmap 维护工作流

| 字段 | 值 |
|------|-----|
| 日期 | 2026-05-04 |
| 里程碑 | C（阶段 3） |
| 真源 | [hermes_mimir_behavior_matrix.md](../hermes_mimir_behavior_matrix.md)、[ralph_parity_testmap.md](../ralph_parity_testmap.md) |

---

## 1. 范围与非目标

**范围**

- 如何把「可对账 Hermes」从口号变成 **可勾选行**：**ID、证据、OK/DIFF/TBD**。
- **HERMES_REF** 变更时的最小流程（矩阵 §0、§3）。

**非目标**

- 不重新审计全表每一行源码；不替代 **`./run_ralph_tier0.sh`**。

---

## 2. 工作流（推荐）

1. **改行为前**：在矩阵找到对应 **ID** 或新增 **Hxx**；**证据** 列写入或更新 pytest 路径。
2. **改行为后**：跑 **`./run_ralph_tier0.sh`**；更新 **MimirAether** 列 **OK/DIFF/TBD**。
3. **同步 testmap**：`ralph_parity_testmap.md` 与矩阵 **H** 行引用保持一致，避免「矩阵写了、映射找不到」。
4. **Hermes 升级**：`git checkout HERMES_REF`（见矩阵 §0）→ diff 行为 → 更新矩阵 **Hermes（REF）** 列 → 再决定 Mimir 是否跟。

---

## 3. 与阶段 3 的关系

- **独立学习** 的默认产出之一是 **读本仓库矩阵 + testmap**，而非必须先有上游仓；上游路径 **`~//.openclaw/projects/hermes-agent`** 为矩阵示例，换机自改。
- **H15** 工具名 diff：**`scripts/diff_tool_names_hermes_mimir.py`** 是矩阵 §5 的配套；退出码 1 为预期直至主动对齐工具面。

---

## 4. 差距与改进建议

1. **H20 CI**：矩阵写 **TBD**；建议在 GitHub Actions 绑定 **`run_ralph_tier0.sh`** 后改 **OK**（另任务）。
2. **阶段 3 索引**：本目录 **README** 与矩阵 §4 互链，减少「报告散落」问题。

---

## 5. 拟迁移项

- 已在 **`hermes_mimir_behavior_matrix.md`** §4 增加 **目标 D（阶段 3）** 指向 **`docs/phase_c_studies/`**。

---

## 6. 复盘

- **学到什么**：**证据列** 是 M1/M6 与产品 parity 的交界；无证据的 OK 不可合并。
- **下一步**：新行为默认先 **GAP/TBD**，再补测降级为 **OK**。
- **风险**：矩阵与代码不同步时，Ralph 绿仍可能「产品不自洽」— 合并前扫一眼相关 **ID**。
