# INCIDENT_TO_TEST — 事故→回归用例映射表

**件**：F5「事故→用例」映射（第 10 单 · A 档 #5）。来源：审计卡 `wiki/discussions/2026-10-06-Mimir工作改进审计-多智能体架构师.md` §4 F5（行 77–80）+ §7（行 136）。
**目的**：每条已发生事故必须对应 **≥1 条可跑回归用例**（SRE · Incident Response Integration：post-incident reviews focused on **systemic fixes**）——否则事故复发时无闸门。
**口径**：`用例` 列一律写 `文件路径::用例名`；本表**零新增用例**，全部复用仓内现成用例。
**校验**：表内每个用例名都可 `grep -rn '<用例名>' tests/` 命中；表内**无占位标记**（占位词清单见审计卡 F4 判据）。
**跑法**：`env HOME=~ bash scripts/pytest_isolated.sh <文件> -q`（重测试必须隔离，见 INC-FORK-ENOMEM）。

| 事故标识 | 一句话现象 | 对应用例（`文件路径::用例名`） |
|---|---|---|
| INC-FORK-ENOMEM | 整机 fork 失败 `Errno 12`：gateway 顶格 4G cgroup 之际起 chroma 回填单元（≈2.8G）⇒ OOM；`terminal` / `read_file` / `write_file` / `search_files` 全死 | `tests/gateway/test_pending_index_startup_hook.py::test_pending_present_resumes_with_limit_and_reports_after`（回填**限流**：`MIMIR_PENDING_INDEX_RESUME_LIMIT` 默认 20）<br>`tests/tools/test_index_incremental_watermark.py::test_pending_marker_written_before_indexing`（**增量水位**：不再整量重建） |
| INC-SILENT-DROP | **写入成功 ≠ 送达**：消费器按 kind 白名单拦，非白名单**静默** `continue`（无日志、不入 seen） | `tests/scripts/test_buzz_send.py::test_envelope_rejects_unknown_kind`（信封契约：kind 必须在枚举内，非枚举**即拒**而非静默丢弃） |
| INC-ZOMBIE-CRON | Gateway 重启后 cron `next_run_at` 变 `null`/冻结 ⇒ `get_due_jobs()` 直接跳过 ⇒ 任务**永久死**且无人被告知 | `tests/scripts/test_check_cron_hygiene.py::test_enabled_with_frozen_next_run_fails`（enabled 却 next_run 冻结 ⇒ 判红） |
| INC-SKELETON-DELIVER | 骨架交付：卡只搭 `§1–§3` 章节壳、正文条目全为空、跑 22 步即收尾；空跑死法 `d85a4c10`（写 tmp 草稿→反复读→吐空正文，未落盘即报「已做」） | `tests/agent/test_placeholder_finish_guard.py::test_positive_guard_blocks_with_reason`（正文含占位 ⇒ 判未完工并出声）<br>`tests/agent/test_empty_run_gate.py::test_armE_regression_readonly_heavy_task_has_artifact`（只读过多必须先落盘） |
| INC-DELIVERY-SILENCE | 投递失败只写 `last_delivery_error` 字段、**无人被告知**；梦境蒸馏出错同病 | `tests/gateway/test_n8_delivery_visibility.py::test_e2e_delivery_failure_reaches_job_state`（投递失败**上浮到 job 状态**，不再只沉淀字段） |

## 备注

- **否证记录**（防「贴标签」）：本表 5 行全部命中**现成**用例 ⇒ 依任务书「优先复用现成用例」，**新增用例 = 0 条**（未为凑数造空壳，未用 skip / xfail 清账）。
- **INC-FORK-ENOMEM 与 INC-DELIVERY-SILENCE 的边界**：前者治「内存 / 回填无界」，后者治「失败只落字段不出声」。两者同源（静默失败）但修法不同，故拆两行。
- **未覆盖面（如实记录 · 非占位）**：`fork ENOMEM` 事故中「**重测试隔离**」这一半的**行为**回归——即 `scripts/pytest_isolated.sh` 在 gateway cgroup 内 `exit 97` 拒跑——**目前无自动化用例**。该分支依赖运行进程自身的 cgroup 归属读数，测试进程内无法受控伪造（改脚本即越本单边界）。现状靠**流程强制**（AGENTS / MEMORY 定为唯一跑法）+ 脚本自带 `[isolated] cgroup=` 自证行人工核对。
