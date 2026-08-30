# Phase 1 — P1-1 胶囊迁移审计摘要

| 字段 | 值 |
|------|-----|
| **日期** | 2026-05-19 |
| **执行** | Cursor 战略窗口（本机审计） |
| **数据根** | `MIMIR_AETHER_HOME=~/.mimiraether` |
| **仓库根** | `~/src/MimirAether` |
| **契约** | [`docs/MIMIR_HTML_MEMORY_CONTRACT.md`](../MIMIR_HTML_MEMORY_CONTRACT.md) §3 |

---

## 1. 结论（给 P1-2 / P1-6 用）

| 指标 | 数量 |
|------|------|
| `mimicore/public/*.md`（归档源） | **131** |
| `$MIMIR_AETHER_HOME/memory/capsules/*.html`（真源） | **230** |
| md → html **已覆盖** | **131 / 131** |
| **缺失**（应有 html 无） | **0** |
| **额外 html**（无对应 md 前缀） | **96** |

**裁定**

- **P1-2 补缺迁移：跳过** — 无需再跑 `scripts/migrate_capsules.py`（除非后续新增 md）。
- **额外 96 个 html**：视为会话中 `produce_capsule` 或后续发布产生，**非迁移遗漏**。
- **P1-6 关单条件**：完成 P1-3（契约抽检）、P1-4（工具冒烟 + tier0 绿）、P1-5（归档声明文档）后即可将 BACKLOG #3 / ISSUES #6 标为完成。

---

## 2. 审计方法

1. 遍历 `mimicore/public/*.md`，解析 YAML frontmatter（与 `scripts/migrate_capsules.py` 一致）。
2. 推导 `capsule_id`（frontmatter 或 `sha256(title+body[:500])[:12]`）。
3. 期望文件名：`{capsule_id[:12]}_{title_slug}.html`（`title_slug` 规则同 migrate 脚本）。
4. 在 `$MIMIR_AETHER_HOME/memory/capsules/` 中匹配：
   - 精确文件名，或
   - 以 `{capsule_id[:12]}_` 为前缀的 html。

复现（仓库根）：

```bash
export MIMIR_AETHER_HOME="${MIMIR_AETHER_HOME:-$HOME/.mimiraether}"
python3 scripts/migrate_capsules.py   # 仅当新增 md 时；当前会全部 skip
```

---

## 3. 路径真源（勿混）

| 路径 | 角色 |
|------|------|
| `{repo}/mimicore/public/*.md` | **只读归档**；禁止作为 publish 源（P1-5 将写入 spring 文档） |
| `$MIMIR_AETHER_HOME/memory/capsules/*.html` | **Canonical 胶囊真源**；`list_capsules` / `get_capsule_by_id` 扫描此目录 |
| `tools/mimircore_tool.py` | `_get_capsules_publish_dir()` → `get_mimir_home()/memory/capsules` |

---

## 4. 下游任务指针

| 步骤 | 文档 / 动作 |
|------|-------------|
| **P1-3** | 随机 10 个 html 抽检 → 产出 `docs/phase1/P1-3-capsule-sample-audit.md` |
| **P1-4** | `list_capsules` + `get_capsule_by_id` 冒烟；`./run_ralph_tier0.sh` |
| **P1-5** | 更新 `MIMIR_MIMICORE_SPRING_SCOPE.md` 或 HTML 契约 §5 归档声明 |
| **P1-6** | `MIMIR_EXEC_BACKLOG.md` #3、`MIMIR_ISSUES.md` #6 → resolved |

---

## 5. 飞书通道（Phase 1 并行参考）

审计日网关状态（**不阻塞 P1**）：

- 进程：`gateway/run.py`，`cwd` = 仓库根
- `gateway_state.json`：`feishu` = `connected`
- 日志：当日多次 `[Feishu] send success`

Phase 2（飞书体验 bug）后置；见 `docs/ISSUES.md`。

---

## 6. 修订

| 日期 | 变更 |
|------|------|
| 2026-05-19 | 初版：P1-1 审计 131/0/96 |
