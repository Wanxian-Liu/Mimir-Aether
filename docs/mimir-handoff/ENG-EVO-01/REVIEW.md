# ENG-EVO-01: Cursor 复核重点

## 1. 最小修复正确性

改动：`post_close_analysis.py:168`

```diff
-                        if not r.success and r.error:
+                        if not r.success:
```

**确保**：删除 `and r.error` 不会在任何路径下导致 `%s` 格式化异常——已在第 175 行预留 `(r.error or "no error detail")[:200]` 兜底。

## 2. 已知未做

- **未解决 `ok=0` 的执行失败根因**：本次只修复了**诊断可见性缺口**（让 detail 日志必出），未修改 `apply_evolution_from_suggestions_async` 内部为什么要写 SKILL.md 失败。  \
  等新的 detail 日志积累后，可定位：
  - `crash_tool`/`orphan_tool` 的 `Action.CAPTURED` 分支是否因技能已存在而静默失败
  - `SkillEvolutionPipeline` 的 `require_confirmation=True`（默认）是否在某些路径下阻止写入
- **未更新 `iq-p3-baseline.json`**：`ok_pct` 会在下一轮周常 M-WEEKLY-02 自然更新
- **未做 M6**：仅改 1 行 log 条件，无功能性变化

## 3. 安全/契约

- 不触达 network、file I/O 路径更改
- 不改变 `SESSION_SEARCH_BACKEND`、`AUTO_EVOLVE` 等任何默认值
- 不涉及 `data/persistent.json`
