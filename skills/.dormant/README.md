# `.dormant/` — 归档区语义（休眠 ≠ 停用）

> B3 落盘（2026-09-13 · Mimir）。本文件是**归档区的唯一语义说明**，两侧同步
> （`~/.mimiraether/skills/.dormant/README.md` 与 `~/src/MimirAether/skills/.dormant/README.md`）。

## 1. 语义

| 目录 | 含义 | 是否加载 | 是否参与质量报警 |
|:--|:--|:--|:--|
| `skills/<category>/<skill>/` | **在役** | ✅ 可被 `skill_view` 加载 | ✅ 是 |
| `skills/.dormant/<category>/<skill>/` | **归档（parked）** | ❌ 不加载 | ❌ **否**（参见下文） |

**休眠 ≠ 停用**：`.dormant` 只表示「当前不加载、不注入」，**不表示内容是错的/废弃的**。
归档区的技能可以是**完整有效**的知识（例如 `mimiraether-context-compressor` 曾在 2026-08-06
被随大流误归档，实为在役机制的排障手册，2026-08-09 已复活）。因此：

- **归档** = 降低注入成本（省 token），不是质量判决；
- **复活** = 把目录移回 `skills/<category>/`，并补一行复活记录（日期/原因/移动路径）。

## 2. 判定法（判断一个技能「该归档」还是「该修」）

**唯一合法判据 = 盘上证据，不是感觉，也不只是 mtime**（2026-09-12 U6 教训：
mtime/无消费标记不足以判死活，曾有 2 个"死副本"实测在役）。

| 步 | 动作 | 命令/落点 | 判据 |
|:--:|:--|:--|:--|
| 1 | 引用盘点 | `grep -rIn "<skill 名>" ~/src/MimirAether/agent ~/src/MimirAether/gateway ~/src/MimirAether/tools` | 被代码 import/字符串引用 → **在役** |
| 2 | 声明盘点 | 检查 `skills/` 下 `SKILL.md` 的 `auto_load:` | `true` → 在役（每轮注入）；`false` → 懒加载，可为归档候选 |
| 3 | 服务指向 | `systemctl --user cat <unit>` 看 `Environment=` / `ExecStart=` 是否指向该路径 | 被服务指向 → **在役**（不是死副本） |
| 4 | 内容判定 | 读正文：是「方法论/排障手册」还是「一次性任务记录」 | 方法论 → 保留或复活；一次性记录 → 归档 |
| 5 | 若复活 | `git mv` + 补复活记录 | 参照 `mimiraether-context-compressor` 的「复活与审计追踪」段 |

**反向判据（禁止）**：仅凭「很久没被加载」就把方法论归档——懒加载技能天然"很久没被加载"。

## 3. 质量报警的作用域（B3 修复）

`SkillsQA.detect_ghost_skills()` 默认 **`include_archived=False`**：

- 归档区含**历史嵌套副本**（`x/x/SKILL.md`，早期移动留下的双层目录），按在役标准判定必然产生
  永远归不了零的报警 → 已从报警口径剔除；
- 归档条目仍可审：`detect_ghost_skills(include_archived=True)`；
- curator 的 INFO 行会记录被排除的归档条目数（可见、不报警）。

**实测口径**（2026-09-13）：`~/src/MimirAether/skills` 在役幽灵 = **0**；含归档 = 15
（11 件 `.dormant` 条目 + 4 件在役缺 frontmatter，后者已补）。

## 4. 已知遗留（未修，登记）

- `.dormant` 内有 13 处**双层嵌套目录**（`<skill>/<skill>/SKILL.md`）：移动残留，内容与上层重复。
  处置需逐件 diff（不可盲删），归入资产治理批次，不在 B3 范围。
- `.dormant/mimiraether/mimir-true-self` 的 frontmatter 缺 `description`（在役侧 `mimir-true-self`
  为 auto_load 身份技能，**不在此处改**，避免影响身份注入）。
