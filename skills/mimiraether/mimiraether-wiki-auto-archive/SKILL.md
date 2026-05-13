---
description: 当 Agent 从 learnings/ 引用知识时自动归档到 wiki。触发权在 Agent，无需用户指令。
---

# mimiraether-wiki-auto-archive

## 触发条件

当以下条件同时满足时自动触发：
1. Agent 使用 `search_files` 或 `read_file` 从 `learnings/` 目录读取了内容
2. 该内容被用于回答用户问题
3. 该知识点值得跨会话复用

## 工作流

```
learnings/ 引用 → 回答用户 → 判断归档 → 落 wiki → 一行告知
```

## 归档目标

| 内容类型 | 落点 |
|----------|------|
| Hermes 模块/组件分析 | `~/wiki/entities/hermes-{name}.md` |
| 架构概念/设计模式 | `~/wiki/concepts/{name}.md` |
| Mimir vs Hermes 对比 | `~/wiki/comparisons/{name}.md` |
| 决策记录 | `~/wiki/concepts/decision-{name}.md` |

## 页面模板

```markdown
---
title: {标题}
created: {日期}
updated: {日期}
type: entity | concept | comparison
tags: [hermes, mimiraether, {领域}]
sources: [learnings/{源文件名}]
---

## 概述
{一句话}

## 核心要点
{从 learnings 提取的关键信息}

## 与 MimirAether 的关系
{关联说明}

## 参考
- learnings/{源文件名}
```

## 判断标准

**归档** ✅：
- 用户明确问到的 Hermes 概念/模块
- 需要跨会话复用的技术决策
- 可能再次引用的对比分析
- 架构设计模式

**不归档** ❌：
- 一次性问答
- 临时调试信息
- 已知信息的重复
- 纯闲聊内容

## 完成后

追加到 `~/wiki/log.md`：
```
## [{日期}] auto-archive | {页面名} ← learnings/{源文件}
```

更新 `~/wiki/index.md` 对应节。

## 告知格式

归档完成后简单告知（一行）：
```
📝 wiki: {页面名} ← learnings/{源文件}
```
