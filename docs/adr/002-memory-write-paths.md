# ADR-002: 记忆写入路径统一（stub）

> **状态**: Phase2 最小实现（ENGINE-P3W-01 · `agent/memory_write_facade.py`）；全路径合并层仍迭代中  
> **日期**: 2026-05-24  
> **来源**: ISSUES #3 | CLARIFY_BASELINE §4 | Prompt 1 收口

---

## 背景

当前存在多条「记忆 / 胶囊 / 进度」落盘路径，行为重叠、真源不唯一：

| 入口 | 典型路径 | 写入者 |
|------|----------|--------|
| HTML 胶囊契约 | `$MIMIR_AETHER_HOME/memory/capsules/` | agent / gateway 发布流 |
| mimicore 遗留 public | `{repo}/mimicore/public/*.md` | 历史只读归档 |
| skill_curator | `data/persistent.json` 子段 | `agent/skill_curator.py` |
| 外部 wiki | llm-wiki / obsidian | 人工或外部工具 |

ISSUES **#3** 标为 **deferred**：Phase 1.5 不扩 scope 做统一实现。

## 决策（暂定）

- **运行时真源**：`MIMIR_AETHER_HOME` 下 `memory/capsules/`（HTML）+ `persistent.json`（进度/技能元数据），见 `docs/MIMIR_HTML_MEMORY_CONTRACT.md`。
- **新发布**：只写 data home；不从 mimicore public 抄默认路径。
- **统一单写者 / 合并层**：Phase 2 候选，依赖 ADR-001 persistent 单写者落地后再设计。

## 后果

- 新窗读 ISSUES Active 时 #3 仅链本文档，不误判为「待修 bug」。
- Prompt 2 建 Phase 0 队列前，不在本 stub 上承诺交付日期。

## 参考

- [ADR-001](./001-persistent-single-writer.md) — persistent 竞态  
- `docs/path-contract.md` — home vs repo  
- `docs/MIMIR_ISSUES.md` — Active #3
