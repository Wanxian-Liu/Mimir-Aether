# 主线进度快照

> **单一更新入口**：用户问「进度 / 主线 / 完成度」时，协作者应先 **Read 本文件**，再根据当前仓库事实与可选命令输出 **更新下列表格与日期**，必要时补一行「本轮变更摘要」。  
> 权威依据：`docs/DEVELOPMENT_NORTH_STAR.md`、`docs/ralph_roadmap_milestones.md`、`成长路线图.md`、`docs/ralph_parity_testmap.md`、`docs/ralph_tier0_case_matrix.md`。

| 字段 | 值 |
|------|-----|
| **最近更新** | 2026-05-01 |
| **更新人** | 协作者（用户问进度时刷新） |
| **仓库根（真源）** | `~/.openclaw/projects/MimirAether` |
| **可选校验** | `./run_ralph_tier0.sh`（门禁）；里程碑 A 项需真环境手动/清单 |

---

## 1. 工程里程碑（Ralph / Parity）

| ID | 名称 | 状态 | 说明 |
|----|------|------|------|
| M0 | 基线可回归 | **绿** | `run_ralph_tier0.sh` 日常可通过；发版前可自检「连续 3 次」 |
| M1 | 契约可执行 | **绿** | `docs/ralph_parity_testmap.md` 已映射；扩展项见 ext / 另增 |
| M2 | Tier-0 矩阵闭合 | **绿** | `ralph_tier0_case_matrix.md`：当前无阻塞 P0；契约变更后需复核 |
| M3 | 垂直切片 | **黄** | 已有 **CLI `run_task` / `-q` 同栈** 切片 + 测试 + 文档（`docs/m3_cli_quick_task_slice.md`）；**第二条**（如 API）仍缺 |
| M4 | Tier-2 HTTP（可选） | **未** | 可选 |
| M5 | 内核可替换 | **未** | 接口化与替换说明 |
| M6 | 进化可审计 | **未** | 进化需绑定 commit / 测试 / 指标 |

状态图例：**绿** = 满足文档完成判据或等价；**黄** = 部分/待复核；**未** = 未达成。

---

## 2. 产品阶段（成长路线图）

| 阶段 | 里程碑 | 状态 | 说明 |
|------|--------|------|------|
| 1 Hermes 影子期 | **A**：CLI + gateway + 工具链 + 基础 RL | **黄** | **CLI 单次任务路径**已有自动化切片（桩 LLM）；gateway / 真网 / RL 仍待 smoke 勾选 |
| 2 专项伙伴期 | B | **未** | 依赖 A |
| 3 独立学习期 | C | **未** | — |
| 4 自主进化期 | ∞ | **未** | — |

---

## 3. 两条主线健康度

| 主线 | 健康度 | 备注 |
|------|--------|------|
| **Parity** | 强 | 契约 + Gate1–3 + 测试映射可追踪 |
| **Evolution** | 弱 | M6 未落地；大改需指标与回归 |

---

## 4. 近期焦点（可改）

1. 补 **`docs/mimir_prod_smoke.md`**（或等价）里程碑 A 真环境 checklist；第二条 M3 切片（`api_service`）可选。
2. 保持 `run_ralph_tier0.sh` 全绿；合入用 Ralph 模式三轮。
3. M6 最小记录模板（commit / 测试子集 / 指标）。

---

## 5. 更新日志（倒序）

| 日期 | 摘要 |
|------|------|
| 2026-05-01 | M3：落地 `agent/test_m3_cli_quick_task_slice.py` + `docs/m3_cli_quick_task_slice.md`，纳入 `run_ralph_tier0.sh`。 |
| 2026-05-01 | 初版：建立本文件；工程 M0–M2 绿、M3–M6 未；阶段 1 黄；Parity 强、Evolution 弱。 |
