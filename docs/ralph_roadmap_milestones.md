# MimirAether Ralph 路线图：里程碑与完成判据

本文把「对齐 Hermes → 分层门禁 → 契约 → 垂直切片 → 自研替换 → 可审计进化」收成**可勾选清单**。与下列文档一致，不重复细则：

- 行为契约：`docs/ralph_parity_contract_v1.md`
- 门禁与 Tier 说明：`docs/ralph_tiers.md`
- Tier-0 用例矩阵：`docs/ralph_tier0_case_matrix.md`

**统一验收命令（当前）**：`./run_ralph_tier0.sh`（Gate1–Gate3）。

---

## 里程碑总览

| 阶段 | 名称 | 你得到的产出物 | 完成判据（必须全部满足） |
|------|------|----------------|--------------------------|
| **M0** | 基线可回归 | 可一键运行的门禁脚本 + Tier-1 E2E（桩 LLM） | `./run_ralph_tier0.sh` 连续 3 次无失败；文档与脚本门定义一致 |
| **M1** | 契约可执行 | Parity Contract 与**测试 ID 的映射表** | 契约 §1 所列模块的 P0 行为，每条要么有 `agent/test_*.py`（或子模块测试）引用，要么在契约中**显式标注「暂缓 + 原因 + 目标日期」**；无「未标注的 P0 空洞」 |
| **M2** | Tier-0 矩阵闭合 | Tier-0 矩阵 B 节 P0 项全部落地或降级 | `docs/ralph_tier0_case_matrix.md` 中「待补齐」P0 清零或改为 P1/P2 并同步契约；Gate2 用例集更新且全绿 |
| **M3** | 垂直切片穿通 | 1～2 条**端到端切片**（从 CLI 或 `api_service` 入口） | 每条切片有：场景说明（1 段）、固定 fixture、≥1 个集成测试；切片在 CI 或本地单命令中可跑；不依赖用户手工点 UI |
| **M4** | 提供商/HTTP 分层（可选 Tier-2） | 录播、mock server 或 VCR 类**稳定桩** | 在**无真实 API key** 或**固定录制**下，覆盖至少一条真实 HTTP 形状（请求/解析/错误码）；失败时日志可定位到层（传输 vs 业务） |
| **M5** | 自研内核可替换 | 核心循环与 IO 边界**接口化** | 同一套 Gate1–Gate3（+ M3 切片）在「替换实现」前后均绿；契约中「允许差异」不扩大；无新增默认隐式外部路径依赖 |
| **M6** | 进化可审计 | 自动化或半自动「变更—测试—指标」记录 | 每次 evolve/大批量自动生成：关联 commit 或 run id、触发的测试子集、与上一轮对比的指标（至少：门禁是否全绿、Tier-0 通过率）；伪进化（无测试、无指标）不可合并为默认流程 |

---

## M0：基线可回归（当前默认目标）

**产出物**

- `run_ralph_tier0.sh` 与 `docs/ralph_tiers.md`、`docs/ralph_parity_contract_v1.md` §5 对齐。
- `agent/test_tier1_e2e_agent.py` 覆盖 `run_conversation` 主路径（桩 LLM）。

**完成判据**

1. `./run_ralph_tier0.sh` 退出码 0。  
2. 连续执行 **3** 次脚本无间歇性失败（稳定性门槛与契约 §5 一致）。  
3. 子模块 `mimicore` 等若纳入父仓库，**不得**因未跟踪 `__pycache__` 等导致父仓库长期 `dirty`（忽略规则或清理流程明确）。

---

## M1：契约可执行（Parity ↔ 测试映射）

**产出物**

- **`docs/ralph_parity_testmap.md`**：契约 §2 / §1 ↔ `agent/test_*.py::用例`；**GAP** 与 **ext** 分区维护。

**完成判据**

1. 契约 §2 每个**必须一致**的行为面，至少有一条映射到具体测试，或注明暂缓。  
2. 不存在「口头 P0、文档无、测试无」的三无项。  
3. 新增行为必须先补映射再合入主分支（团队约定写进 §6 或 CONTRIBUTING 一段即可）。

---

## M2：Tier-0 矩阵闭合

**产出物**

- 更新 `docs/ralph_tier0_case_matrix.md`：A 节扩展；B 节 P0 清空或降级有记录。

**完成判据**

1. 矩阵中曾标记的 P0（CLI 边界、delegate、code_execution 环境、turn_loop 预算、registry 并发等）均有自动化覆盖或正式降级说明。  
2. `run_ralph_tier0.sh` 中 Gate2 列表与仓库实际测试文件一致（无遗漏、无已删文件）。

---

## M3：垂直切片穿通

**产出物**

- `docs/` 中小节或 `agent/test_integration_*.py`（名称自定）：每条切片 1 页以内说明 + 测试。

**建议切片示例（二选一即可起步）**

- CLI：`python cli.py …` 单次任务路径到 agent 返回。  
- API：`api_service` 一条与 OpenAI 兼容的 chat 请求（可用 TestClient + 桩模型）。

**完成判据**

1. 每条切片：**入口固定、断言可重复、无人工步骤**。  
2. 切片失败时，能判断是「入口/路由」还是「agent 内核」问题（测试分层清晰）。

---

## M4：Tier-2 HTTP（可选）

**产出物**

- 录制文件目录或 mock 服务启动脚本；文档说明如何刷新录制。

**完成判据**

1. 默认 CI 不依赖外网与真实 key。  
2. 至少覆盖一种真实失败形态（如 401/429/超时）的**结构化处理**断言。

**最小切片（本仓库已落地）**：`agent/auxiliary_client.py` 中 `_is_payment_error` / `_is_connection_error` 离线断言，见 `docs/m4_auxiliary_http_slice.md` 与 `agent/test_m4_auxiliary_http_slice.py`（无外网、无 key）。录播 / mock HTTP / VCR 为后续增量。

---

## M5：自研内核可替换

**产出物**

- 边界接口（例如：模型调用适配器、工具调度、会话存储）与实现类分离；替换说明一页。

**完成判据**

1. 在**不修改测试断言语义**的前提下，可切换实现并通过 M0–M3（及 M4 若启用）。  
2. 契约 §4「不允许差异」零违反。

**最小切片（本仓库已落地）**：显式 **`LlmInvocationPort`**（`agent/llm_port.py`）与离线协议测试，见 `docs/m5_kernel_replaceability_slice.md`；生产路径仍为 `_call_model_with_tokens`，依赖注入与工具/会话端口为后续增量。

---

## M6：进化可审计

**产出物**

- 一次「进化运行」的最小记录模板（markdown/json 均可）+ 存放位置约定。  
- **本仓库落地**：`docs/M6_EVOLUTION.md`（规则）、`docs/evolution_log.md`（追加日志）、`scripts/record_m6_evolution.sh`（跑 `./run_ralph_tier0.sh` 并追加一行）。

**完成判据**

1. 默认流程下，没有「只有代码 diff、没有测试与指标」的合并。  
2. 回归可追溯到具体运行 id 或 commit。

---

## 建议节奏（非强制）

| 周期 | 焦点 |
|------|------|
| 每周 | 推进 M1 映射 3～5 条；保持 `./run_ralph_tier0.sh` 全绿 |
| 每两周 | 闭合 M2 中 1～2 个 P0 |
| 每月 | 增加或巩固 1 条 M3 切片；视需要启动 M4 |

---

## 全部完成后的状态（对照用户问题的一句话）

完成 **M0–M6** 后，你拥有：**与 Hermes 在书面契约范围内行为对齐、分层测试可证明、可替换内核、进化可追溯的 MimirAether 底座**；不是「能 demo」，而是**能签字交付与长期迭代**的工程状态。

若某一阶段策略调整（例如永久不做 M4），须在契约或本文件中**显式降级**，避免口头计划与仓库真相不一致。
