# MimirAether 问题追踪

> 模板：`| # | 日期 | 来源 | 描述 | 严重度 | 状态 |`  
> **规则**：新增 issue 必须带 **Backlog ID**（如 E-012、CLOSE-3、EV-M02）；卡住时在此登记后停手等刘哥确认。  
> **真源队列**：`docs/MIMIR_EXEC_BACKLOG.md` · 主线快照：`docs/MAINLINE_STATUS.md`

---

## Active（≤3）

| # | 日期 | 来源 | 描述 | 严重度 | 状态 | Backlog |
|---|------|------|------|--------|------|---------|
| 13 | 2026-05-31 | OPS-L2-FEISHU-01 | L2 `<retrieved-sessions>` `/new` 后未注入：session_key 与 gateway 不一致 + dotenv 覆盖 HERMES | 中 | closed | OPS-L2-FEISHU-01 |
| 3 | 2026-05-16 | CLARIFY_BASELINE §4 | 记忆落盘三条入口未统一（mimicore public/、skill_curator、llm-wiki/obsidian）— 设计债，见 ADR | 中 | deferred | [adr/002-memory-write-paths.md](./adr/002-memory-write-paths.md) |

---

## 已关闭（归档）

| # | 日期 | 来源 | 描述 | 严重度 | 状态 | 关闭依据 |
|---|------|------|------|--------|------|----------|
| 1 | 2026-05-16 | CLARIFY_BASELINE §3.3 | `list_capsules` 返回 0 — 路径正确，`memory/capsules/` 空因未发布胶囊 | 高 | resolved | 真源路径已验 |
| 4 | 2026-05-16 | 会话实测 | `persistent.json` 截断 — 双写竞争；根因已标 architectural；缓解已到位 | 高 | root-caused | [adr/001-persistent-single-writer.md](./adr/001-persistent-single-writer.md) |
| 5 | 2026-05-16 | 会话实测 | `memory` 工具 `MemoryStore` 未实例化 — `get_memory_store()` 已合，Gateway 验证通过 | 高 | resolved | E-005 前后冒烟 |
| 6 | 2026-05-16 | BACKLOG #1 | 存量胶囊迁移 mimicore/public → `memory/capsules/*.html` | 中 | resolved | P1-6 / BACKLOG #8 |
| 7 | 2026-05-20 | T-09 (d5) | JEPA `run_cycle` 已接 pipeline close（**E-012**, `MIMIR_JEPA_CYCLE`）；skill FIX 仍走 **E-009** | 低 → 中 | resolved | **E-012** 2026-05-24 |
| 8 | 2026-05-20 | T-11 (d7) | `CLI_CONFIG` ImportError — **E-004** 默认值 + 导入路径修复 | 中 | resolved | **E-004** 2026-05-23 |
| 9 | 2026-05-20 | T-10 (d6) | 可观测 TOOL_CALL SQL + monitor + `/health`；NameError **E-010** | 中 | resolved | **E-006** / **E-010** / **E-011b** |
| 11 | 2026-05-21 | EV-L13 | RED Duration P50/P95/P99 缺失 | 低 | resolved | **E-011b** |
| 10 | 2026-05-20 | T-08 (d4) | TRUNCATE：STAB-04 已修；**since-start** 运维 KPI → **documented exception**（非 Active） | 中 | documented exception | **OBS-B1-03** · [`obs-b1-03-issue10-closeout.md`](./phase0/obs-b1-03-issue10-closeout.md) |
| 12 | 2026-05-26 | IQ-EVO-38 | **智商/进化方向** — Wave 6 全 **[x]** · rubric **4.8/10**（documented exception，距 5.5 差 0.7） | 低 | resolved | [`p2-long-iqevo-wave6-closeout.md`](./phase0/p2-long-iqevo-wave6-closeout.md) |
| 2 | 2026-05-16 | CLARIFY_BASELINE §5 | 并行树 `~/.openclaw/projects/MimirAether` — **工程真源** `~/src/MimirAether` | 中 | resolved (process) | CLEARANCE-DONE 2026-05-25 |
