# MimirAether 问题追踪

> 模板：`| # | 日期 | 来源 | 描述 | 严重度 | 状态 |`
> 卡住时在此新增条目，然后停手等确认。

| # | 日期 | 来源 | 描述 | 严重度 | 状态 |
|---|------|------|------|--------|------|
| 1 | 2026-05-16 | CLARIFY_BASELINE §3.3 | `list_capsules` 返回 0 — 结论：代码路径正确，`memory/capsules/` 为空是因从未发布过胶囊，非路径断裂 | 高 | resolved |
| 2 | 2026-05-16 | CLARIFY_BASELINE §5 | `~/.openclaw/projects/MimirAether` 大型并行树存在，易误操作 | 中 | open |
| 3 | 2026-05-16 | CLARIFY_BASELINE §4 | 记忆落盘三条入口未统一（mimicore public/、skill_curator capsule.md、llm-wiki/obsidian 外部） | 中 | open |
| 4 | 2026-05-16 | 会话实测 | `persistent.json` 被截断（324行→5行）。根因：`skill_curator._save_persistent()` 裸读写全量覆盖，与 `cross_session_memory.save()` 双写竞争无合并。属架构断层（两个模块各自维护落盘逻辑），非简单并发 bug。标注 `architectural` / `needs-design`。当前 damage 已恢复，下次截断前有充裕时间设计正确方案 | 高 | root-caused |
| 5 | 2026-05-16 | 会话实测 | `memory` 工具 `MemoryStore` 从未实例化 — 刘哥加 `get_memory_store()` 单例懒加载，Gateway 重启后验证通过。memory 工具端到端可用 | 高 | resolved |
| 6 | 2026-05-16 | BACKLOG #1 | 存量胶囊迁移：`mimicore/public/` 约120枚 `.md` 旧格式胶囊 → `memory/capsules/*.html` 新契约 | 中 | open |
