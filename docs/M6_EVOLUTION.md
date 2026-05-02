# M6 — 进化可审计（最小闭环）

与 `docs/ralph_roadmap_milestones.md` **M6** 对齐：**每次值得合并的「进化」**应能回答「跑了什么、是否回归绿、关联哪次提交」。

## 存放位置

| 产物 | 路径 |
|------|------|
| **追加式日志（真源）** | `docs/evolution_log.md` |
| **本说明 + 模板** | `docs/M6_EVOLUTION.md` |

## 何时必须记一行

- **默认**：任何进入 `main` 的 PR，若 diff 触及 **agent / gateway / tools / 契约测试** 之一，合并前应有一条新日志（或 PR 描述中嵌入同结构表格行，由合并人复制进 `evolution_log.md`）。
- **豁免**：纯文档 typo、仅 `skills/` 文案、与运行时无关的注释 —— 可在日志摘要写 `exempt: docs-only`。

## 一键记录（推荐）

在仓库根执行（会跑完整 `./run_ralph_tier0.sh`，约数十秒）：

```bash
./scripts/record_m6_evolution.sh "一句话说明本轮变更意图"
```

退出码与门禁一致：`0` = tier0 全绿；非 `0` = 仍写入日志（诚实记录失败跑），便于事后审计。

## GitHub PR 模板

合并开 PR 时，作者按模板勾选 **M6** 与 **tier0**：见 **`.github/pull_request_template.md`**。

## 手工模板（脚本不可用时）

复制到 `docs/evolution_log.md` 表格**上方**（新行插在表头下一行，保持倒序可在表尾追加，本仓库约定 **表尾追加**）：

```text
| `<run_id>` | `<UTC ISO8601>` | `<git rev>` | ./run_ralph_tier0.sh | `<exit>` | `<summary>` |
```

- `run_id`：建议 `YYYYMMDDThhmmssZ_<short_rev>`。
- `git rev`：`git rev-parse --short HEAD`，工作区脏可加后缀 `-dirty`。

## 指标（可选）

有量化指标时在同一 PR 或本行 `summary` 用分号附上，例如：`tool_ok_rate 0.94→0.96`。无指标时写 `metrics: n/a` 即可 —— **禁止**无记录合并（见 `docs/DEVELOPMENT_NORTH_STAR.md` §2.2 伪进化信号）。
