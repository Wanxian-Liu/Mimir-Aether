# Task 4: 记忆持久 (Memory Persistence)

> 权重: 20% | 满分: 15

## 任务描述

> ⚠️ **重要**: 此任务模拟跨会话场景。请将以下信息**持久化存储**——保存到文件或你自己的记忆系统中。下一次会话会有人来问这些问题。

### 需要记住的信息

在 `/tmp/benchmark-sandbox/memory/` 下，创建一个文件 `session_memory.json`，存储以下信息：

```json
{
  "project_name": "AetherFlow",
  "port": 9090,
  "database": "PostgreSQL",
  "created_by": "benchmark-runner",
  "created_at": "<ISO timestamp>"
}
```

### 验证问题（下个会话会问）

这些问题的答案你应该已经存储好了：
1. 项目叫什么名字？
2. 端口是多少？
3. 用的什么数据库？

---

## 评分标准

| # | 检查点 | 分值 |
|---|--------|------|
| 1 | `session_memory.json` 存在且 JSON 有效 | 3 |
| 2 | `project_name` == "AetherFlow" | 4 |
| 3 | `port` == 9090 | 4 |
| 4 | `database` == "PostgreSQL" | 4 |

**最高: 15 分**
