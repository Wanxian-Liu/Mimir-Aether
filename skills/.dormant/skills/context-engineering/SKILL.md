---
name: context-engineering
description: "Google ADK 上下文工程——context as compiled view（分层/压缩/缓存/artifacts/记忆检索）。管理 agent 上下文/防上下文爆炸/上下文优化时用。"
version: 1.0.0
metadata:
  hermes:
    tags: [context, engineering, adk, google, 上下文管理]
    category: knowledge
---

# Context Engineering（Google ADK——上下文编译视图）

> **来源**：Google for Developers《Architecting efficient context-aware multi-agent framework for production》（2026——全文在 `~/wiki/raw/agent-architecture/B2-*`）
> **核心论点**：**"把所有东西塞进一个巨型 prompt"必然崩溃**——上下文要像系统一样架构（分层/编译/生命周期）——不是靠更大窗口

## 核心心智模型：Context as a compiled view

**上下文 = 对底层有状态系统的"编译视图"**——不是可变字符串缓冲区：
```
存储（Session——ground truth）→ 处理器管线（编译）→ 工作上下文（每轮重建的投影）
```

## 三大设计原则

### 1. 结构化分层（tiered model）
| 层 | 职责 |
|:--|:--|
| **Session（存储）** | 强类型 Event 流（消息/工具调用/结果/错误）——ground truth |
| **Working Context（工作上下文）** | 每轮从 Session 重建的投影（指令+身份+选中事件+记忆结果）——**临时/可配置/模型无关** |
| **Flows/Processors（编译管线）** | request/response 处理器有序链——过滤/压缩/缓存/路由的插入点——**不再改写巨型模板——增删处理器** |

### 2. 相关性（relevance——什么该进窗口）
- **Artifacts（大型数据句柄化）**：大 payload（5MB CSV/PDF）放 Artifact 存储——上下文只留轻量引用——需要时才 LoadArtifactsTool 加载——用完即卸载（**ephemeral expansion**）——"5MB 噪声"→"按需精确加载"
- **Memory（长期知识按需检索）**：搜索式（不永久钉住）——agent 定向检索（load_memory_tool/preload_memory_tool）——**替代 context stuffing 反模式**
- **人+agent 协作**：人定架构（数据在哪/怎么摘要/什么过滤）——agent 决定动态"reach"什么

### 3. 压缩与缓存（scaling）
- **Compaction**：阈值触发（调用次数）→ LLM 摘要旧事件（滑窗+重叠）→ 摘要写回 Session 作为新事件（prune/de-prioritize 原始事件）——**操作在 Event 流上——级联收益**
- **Filtering**：确定性规则插件全局裁剪（在到达模型前）
- **Context Caching**：前缀缓存——静态指令（static instruction）保证不变段在前面——动态内容靠后——**缓存前缀复用——省硬件重算**

## 可操作清单（对我们/Mimir）

1. **存储与展示分离**：Session 是 ground truth——工作上下文是投影——不硬编码 prompt
2. **句柄模式**：大文件/大数据 → 引用（名字+摘要）→ 需要时加载 → 用完卸载——**Mimir 读大卡时用**（不整卡塞上下文）
3. **检索式记忆**：不 context stuffing——按需 load_memory——**第二大脑就是这个**（语义搜索检索）
4. **压缩在事件层**：摘要写回历史（不是丢弃）——**Mimir P2-1 压缩（150K+验证钩子）方向正确**——可补"摘要写回事件流"
5. **缓存友好**：系统提示/静态指令稳定在前——动态内容在后——省 token（DeepSeek 缓存 0.1x 价）

## 反模式
- ❌ 上下文 dumping（大 payload 全塞历史——每轮拖累）
- ❌ 无结构单窗口（一切塞一个 prompt）
- ❌ 记忆永久钉住（该检索的不钉）
- ❌ 压缩丢信息（该写回的不写回）
