# IQ-55 进化管道下一迭代方向

> 记录时间：本会话验收后
> 状态：待讨论，非任务

## 当前状态

进化管道已从 `blocked` → `healthy`。账本 18 条，2 条 `evolved`（`outcome=success`）。

## 核心问题

`execute_callback` 当前只在候选文件中补无意义 docstring（`"function auto-docstring"`）——能让引擎跑通校验，但**无实际价值**。

## 有价值的迭代方向（按优先级）

### P0: 让 execute_callback 做真实改进

不再补占位 docstring，改为可验证的有价值微改：

| 类型 | 示例 | 验证方法 |
|:----:|------|:--------:|
| 🏷️ 补类型标注 | `def foo(x) -> str:` | `mypy --strict` 通过 |
| 🛡️ 补防卫性检查 | `if path is None: raise ValueError(...)` | 契约测试 |
| 🧹 修复路径硬编码 | `"data/..."` → 从 config 读 | path-contract 扫描 |
| 📝 补真实 docstring | 说明参数/返回/异常 | 不含「auto-docstring」字样 |

### P1: 进化质量评估

- 每次 `evolved` 后计算 diff 行数/价值
- 过滤掉无意义改动（行数 <3 或 docstring 内容为 `"function auto-docstring"`）
- 账本增加 `quality_score` 字段（0-10）

### P2: 回滚机制

- `evolved` 改动若导致后续 tier0 失败 → 自动 `git checkout --` 回滚
- 账本标注 `rolled_back` 状态

## 不做的事

- ❌ 不让 evolution 主动改 `agent_loop.py` 或 `gateway/`（IC 规则已保护）
- ❌ 不依赖 Cursor 做进化（设计为刘哥本地可跑）
- ❌ 不补无意义 docstring（已发现并禁用）

---

*讨论材料，非执行计划。*
