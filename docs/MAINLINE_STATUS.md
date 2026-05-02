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
| M3 | 垂直切片 | **绿** | **两条**：CLI（`docs/m3_cli_quick_task_slice.md`）+ **API** `POST /v1/chat/completions`（`docs/m3_api_chat_slice.md`，`agent/test_m3_api_chat_slice.py`） |
| M4 | Tier-2 HTTP（可选） | **黄** | 最小切片：辅助 HTTP 错误分类离线测试 + 文档（`docs/m4_auxiliary_http_slice.md`）；全绿需更广 Tier-2 HTTP / 录制见里程碑正文 |
| M5 | 内核可替换 | **未** | 接口化与替换说明 |
| M6 | 进化可审计 | **黄** | **`docs/M6_EVOLUTION.md`** + **`docs/evolution_log.md`** + **`scripts/record_m6_evolution.sh`** 已落地；合并触达 agent/gateway/tools/契约测时须补记一行。**绿** = 团队默认执行满 2 个合并周期无漏记 |

状态图例：**绿** = 满足文档完成判据或等价；**黄** = 部分/待复核；**未** = 未达成。

---

## 2. 产品阶段（成长路线图）

| 阶段 | 里程碑 | 状态 | 说明 |
|------|--------|------|------|
| 1 Hermes 影子期 | **A**：CLI + gateway + 工具链 + 基础 RL | **绿** | Smoke：A1–A4 已验；**飞书** Bot「wan」真实消息已通（`mimir_prod_smoke.md`） |
| 2 专项伙伴期 | B | **未** | 依赖 A |
| 3 独立学习期 | C | **未** | — |
| 4 自主进化期 | ∞ | **未** | — |

---

## 3. 两条主线健康度

| 主线 | 健康度 | 备注 |
|------|--------|------|
| **Parity** | 强 | 契约 + Gate1–3 + 测试映射可追踪 |
| **Evolution** | 中 | M6 最小闭环已落地；习惯养成中（见 `docs/evolution_log.md`） |

---

## 4. 近期焦点（可改）

1. **执行 M6**：合并前对「agent / gateway / tools / 契约测试」类 PR 运行 `./scripts/record_m6_evolution.sh "…"` 或等价手工行。
2. 保持 `run_ralph_tier0.sh` 全绿；合入用 Ralph 模式三轮（若启用严格迭代）。
3. M6 标 **绿** 前：连续 2 个合并周期无漏记（自证习惯）。

---

## 5. 更新日志（倒序）

| 日期 | 摘要 |
|------|------|
| 2026-05-01 | **M4 黄**：`agent/test_m4_auxiliary_http_slice.py` + `docs/m4_auxiliary_http_slice.md`，纳入 `run_ralph_tier0.sh`；分类层离线断言（401 / 429 语义 / 超时形状）。 |
| 2026-05-02 | **M6 黄**：新增 `docs/M6_EVOLUTION.md`、`docs/evolution_log.md`、`scripts/record_m6_evolution.sh`，`AGENTS.md` 合并指引；tier0 当次全绿。 |
| 2026-05-02 | M3 **第二条**：`agent/test_m3_api_chat_slice.py` + `docs/m3_api_chat_slice.md`，纳入 `run_ralph_tier0.sh`；M3 标 **绿**。 |
| 2026-05-02 | 飞书连接成功（Bot「wan」）；里程碑 **A** 标 **绿**。 |
| 2026-05-01 | 里程碑 A smoke 首轮：代理回报写入 `mimir_prod_smoke.md`；A2 真实消息仍缺，阶段 1 保持黄。 |
| 2026-05-01 | 新增 `docs/mimir_prod_smoke.md`：里程碑 A（A1–A4）真环境勾选表。 |
| 2026-05-01 | M3：落地 `agent/test_m3_cli_quick_task_slice.py` + `docs/m3_cli_quick_task_slice.md`，纳入 `run_ralph_tier0.sh`。 |
| 2026-05-01 | 初版：建立本文件；工程 M0–M2 绿、M3–M6 未；阶段 1 黄；Parity 强、Evolution 弱。 |
