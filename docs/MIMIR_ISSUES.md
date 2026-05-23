# MimirAether 问题追踪

> 模板：`| # | 日期 | 来源 | 描述 | 严重度 | 状态 |`
> 卡住时在此新增条目，然后停手等确认。

| # | 日期 | 来源 | 描述 | 严重度 | 状态 | 老化(2026-05-21) |
|---|------|------|------|--------|------|-------------------|
| 1 | 2026-05-16 | CLARIFY_BASELINE §3.3 | `list_capsules` 返回 0 — 结论：代码路径正确，`memory/capsules/` 为空是因从未发布过胶囊，非路径断裂 | 高 | resolved | ✅ 可关闭（已 resolve 5d+） |
| 2 | 2026-05-16 | CLARIFY_BASELINE §5 | `~/.openclaw/projects/MimirAether` 大型并行树存在，易误操作 | 中 | open | 🔄 保持（并行树未清理） |
| 3 | 2026-05-16 | CLARIFY_BASELINE §4 | 记忆落盘三条入口未统一（mimicore public/、skill_curator capsule.md、llm-wiki/obsidian 外部） | 中 | open | 🔄 保持（三入口仍在） |
| 4 | 2026-05-16 | 会话实测 | `persistent.json` 被截断（324行→5行）。根因：`skill_curator._save_persistent()` 裸读写全量覆盖，与 `cross_session_memory.save()` 双写竞争无合并。属架构断层（两个模块各自维护落盘逻辑），非简单并发 bug。标注 `architectural` / `needs-design`。当前 damage 已恢复，下次截断前有充裕时间设计正确方案 | 高 | root-caused | ✅ 可关闭（root-caused 5d+；缓解措施已到位） |
| 5 | 2026-05-16 | 会话实测 | `memory` 工具 `MemoryStore` 从未实例化 — 刘哥加 `get_memory_store()` 单例懒加载，Gateway 重启后验证通过。memory 工具端到端可用 | 高 | resolved | ✅ 可关闭（已 resolve 5d+） |
| 6 | 2026-05-16 | BACKLOG #1 | 存量胶囊迁移：`mimicore/public/` 约120枚 `.md` 旧格式胶囊 → `memory/capsules/*.html` 新契约 | 中 | resolved | ✅ 可关闭（已 resolve 5d+） |
| 7 | 2026-05-20 | T-09 (d5) | JEPA/self_evolution 已合 main；skill FIX 单通路已接 pipeline（E-009）；**SelfEvolutionEngine.run_cycle** 仍未接 loop | 低 → 中 | **partial-loop** | 🔄 FIX 通路已验；JEPA run_cycle 待接 |
| 8 | 2026-05-20 | T-11 (d7) | ~~`CLI_CONFIG` ImportError~~ — E-004：`mimir_cli.config.CLI_CONFIG` 默认值 + callbacks 改从 `mimir_cli.config` 导入 | 中 | resolved | ✅ E-004 WIN-1 2026-05-23 |
| 9 | 2026-05-20 | T-10 (d6) | 可观测：TOOL_CALL SQL + monitor 阈值 + /health agent 指标已合（E-006）；NameError import 债 E-010 已补 gateway._shared 模块级绑定 + 烟测 | 中 | resolved | ✅ E-010 2026-05-23 |
| 10 | 2026-05-20 | T-08 (d4) | Agent 崩溃：21次 Agent error，栈集中在 gateway/run.py L3593/8422；deepseek vision image_url 不支持；TRUNCATE=19 基线稳定 | 高 | open | 🔄 保持（运行时异常随时复发） |
| 11 | 2026-05-21 | EV-L13 (§13) | RED 三缺一：可观测已覆盖 Rate+Errors（D6-0a/D6-0b），Duration 百分位数（P50/P95/P99 tool call 延迟）缺失 — 供 E-006 后续迭代 | 低 | resolved | **E-011b** — `agent/monitor.py` + `/health` 暴露 `agent_tool_p50/p95/p99_ms` |
