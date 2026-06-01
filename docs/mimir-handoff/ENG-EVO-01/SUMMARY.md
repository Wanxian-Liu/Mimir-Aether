# ENG-EVO-01: 真实 session evolution ok=1 · 归因 & 最小修复

## 做了什么

**归因 1 条生产 `ok=0`**：Session `9ee6d577-24fb-4832-8685-2457a85e06c1`（2026-06-01 00:31，任务"bad tool"），
`applied=2 ok=0`——LLM 后执行分析产生了 2 条进化建议（针对 crash_tool/orphan_tool 0%），
但 **2 条全部失败且未记录失败原因**。

**根因链**：
1. Pipeline close 报告 `should_evolve=false`（error_count=0），但 `degraded_tools` 触发 post-close analysis
2. LLM 分析自行产生 2 条 fix 建议（非 fallback）
3. `apply_evolution_from_analysis` 执行 2 次都失败
4. **日志漏记**：`post_close_analysis.py:168` 条件 `if not r.success and r.error:` 在 `r.error` 为空时抑制了全部 detail 日志
5. 运维人员无法诊断 `ok=0` 的根因——这是一个**自掩埋的诊断缺口**

**最小修复**：删除 `and r.error` 条件，使失败的 evolution 总有 detail 日志（即使 `error=""` 也输出 `"no error detail"`）。

**额外发现**：同一 Gateway 周期已产出 2 条 `ok=1`（session `ce2533cd3382ea78` 和 `c7e8b0b3d441eb81`），
证实进化流水线整体可工作。`ok=0` 主要分布在开关首次上生产的前期 session。

## 风险

极低——仅改了1行条件判断，不影响任何功能逻辑。

## 建议 commit message

```
fix(evolution): log detail when evolution applied fails silently

post_close_analysis.py:168 had `if not r.success and r.error` which
suppresses the detail log when r.error is empty string/None. This
makes it impossible to debug production ok=0 entries.

Remove the `and r.error` gate; fallback to "no error detail" text
when error is falsy.
```
