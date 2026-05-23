# Agent Core 职责映射审计

**日期**：2026-05-21  
**来源**：EV-A01（琬弦架构方案方向一 — Agent Core 职责重划 P0）

## 6 文件职责矩阵

| # | 文件 | 行数 | 主职责 | 次要职责 | 重叠度 |
|---|------|------|--------|---------|:--:|
| 1 | `core_loop.py` | ~2000 | 消息调度、turn 管理、历史维护 | 会话结束/持久化/compressor 调用 | 🟡 中 |
| 2 | `agent_loop.py` | ~400 | Agent 循环（决策→工具→回写） | 部分消息调度逻辑重复 core_loop | 🔴 高 |
| 3 | `turn_loop.py` | ~200 | 单轮 turn 预算控制 | — | 🟢 低 |
| 4 | `prompt_builder.py` | 1560 | System prompt 构建、技能注入、安全扫描 | 上下文文件加载、YAML 解析 | 🟡 中 |
| 5 | `recovery_mixin.py` | ~150 | 异常恢复（TRUNCATE/COMPRESS 决策） | — | 🟢 低 |
| 6 | `context_compressor.py` | 877 | 在线压缩（摘要/裁剪/工具对保护） | — | 🟢 低 |

## 调用链路

```
Gateway 消息 → core_loop (调度)
  ├─ agent_loop (决策循环)
  │   └─ turn_loop (单轮预算)
  ├─ prompt_builder (构建 system prompt)
  │   └─ 安全扫描 (scan_context_content)
  ├─ context_compressor (压缩旧消息)
  └─ recovery_mixin (异常时决策)
```

## 重叠度分析

| 重叠区域 | 涉及文件 | 问题 | 严重度 |
|---------|---------|------|:--:|
| 消息调度 | `core_loop` + `agent_loop` | 两个循环都有消息分发/工具调用的中介逻辑 | 🔴 |
| 安全扫描 | `prompt_builder` | `scan_context_content()` 嵌入在 prompt_builder 中，而非独立 guard 层 | 🟡 |
| 压缩触发 | `core_loop` + `context_compressor` | `should_compress()` 调在 core_loop 中，但阈值在 compressor 里 | 🟡 |

## 对应架构方案方向一的拆分建议

| 方案动作 | 涉及文件 | 优先级 |
|---------|---------|:--:|
| 新建 `orchestrator.py` — 统一消息编排 | `core_loop` + `agent_loop` | 🔴 P0 |
| 重构 `engine.py` — 决策+执行分离 | `core_loop` | 🔴 P0 |
| 升级 `dialogue_mgr.py` — 会话管理独立 | `core_loop` | 🟡 P1 |
| 拆分 prompt_guard | `prompt_builder` → `agent/guard/` | 🟡 P1 |

## 结论

**重叠度约 35%**（主要痛点：core_loop 与 agent_loop 的消息调度重复）。方向一最有价值的拆分是 **orchestrator.py**（统一消息编排），可将两个循环的调度逻辑收归一处。prompt_guard 拆分（EV-A05 确认）是最安全的切入点。
