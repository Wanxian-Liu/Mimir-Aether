# Session模块差距分析

## 概述

| 维度 | hermes-agent | MimirAether | 差距 |
|------|---------------|-------------|------|
| 架构 | SQLite-backed SessionStore | In-memory SessionManager | 大 |
| 复杂度 | 高度完整 | 基础实现 | 大 |
| 功能 | 生产级 | 原型级 | 大 |

## 详细对比

### 1. 核心数据结构

| 类/函数 | hermes-agent | MimirAether | 状态 |
|---------|-------------|-------------|------|
| `SessionSource` | ✅ 描述消息来源 | ❌ 无 | 缺失 |
| `SessionContext` | ✅ 完整会话上下文 | ❌ 无 | 缺失 |
| `SessionEntry` | ✅ 存储条目(含token统计) | ⚠️ `Session` 简化版 | 部分缺失 |
| `SessionStore` | ✅ SQLite持久化+内存缓存 | ⚠️ `SessionManager` 仅内存 | 功能差异 |
| `build_session_key()` | ✅ 确定性key构建 | ❌ 无 | 缺失 |
| `build_session_context()` | ✅ 构建上下文 | ❌ 无 | 缺失 |

### 2. PII处理

| 功能 | hermes-agent | MimirAether | 状态 |
|------|-------------|-------------|------|
| `_hash_id()` | ✅ 确定性12字符hash | ❌ 无 | 缺失 |
| `_hash_sender_id()` | ✅ user_<12hex>格式 | ❌ 无 | 缺失 |
| `_hash_chat_id()` | ✅ 保留platform前缀 | ❌ 无 | 缺失 |
| `_PII_SAFE_PLATFORMS` | ✅ 定义安全平台 | ❌ 无 | 缺失 |
| `build_session_context_prompt()` | ✅ 带PII处理的prompt构建 | ❌ 无 | 缺失 |

### 3. 会话生命周期

| 功能 | hermes-agent | MimirAether | 状态 |
|------|-------------|-------------|------|
| `get_or_create_session()` | ✅ 评估reset策略 | ✅ 基础TTL | 策略差异 |
| `update_session()` | ✅ 更新metadata+token统计 | ✅ 更新context/state | 部分实现 |
| `reset_session()` | ✅ 强制重置 | ❌ 无 | 缺失 |
| `suspend_session()` | ✅ 暂停会话(防stuck loop) | ❌ 无 | 缺失 |
| `switch_session()` | ✅ 切换到指定session | ❌ 无 | 缺失 |
| `delete_session()` | ✅ 删除会话 | ✅ 删除会话 | 一致 |
| `suspend_recently_active()` | ✅ 启动时暂停活跃会话 | ❌ 无 | 缺失 |

### 4. 重置策略

| 功能 | hermes-agent | MimirAether | 状态 |
|------|-------------|-------------|------|
| `_is_session_expired()` | ✅ 检查idle/daily/both | ❌ 无 | 缺失 |
| `_should_reset()` | ✅ 返回reset原因 | ❌ 无 | 缺失 |
| `SessionResetPolicy` | ✅ 完整策略(mode/at_hour/idle_minutes) | ⚠️ 仅TTL | 大幅简化 |
| 活跃进程检测 | ✅ `has_active_processes_fn` | ❌ 无 | 缺失 |
| 自动重置标记 | ✅ was_auto_reset/auto_reset_reason | ❌ 无 | 缺失 |

### 5. 存储层

| 功能 | hermes-agent | MimirAether | 状态 |
|------|-------------|-------------|------|
| SQLite (`hermes_state.SessionDB`) | ✅ 完整 | ❌ 无 | 缺失 |
| JSONL transcript | ✅ 兼容遗留 | ❌ 无 | 缺失 |
| `append_to_transcript()` | ✅ 双重写入 | ❌ 无 | 缺失 |
| `rewrite_transcript()` | ✅ 用于retry/undo/compress | ❌ 无 | 缺失 |
| `load_transcript()` | ✅ 智能选择数据源 | ❌ 无 | 缺失 |
| sessions.json | ✅ 索引持久化 | ❌ 无 | 缺失 |

### 6. Token统计

| 功能 | hermes-agent | MimirAether | 状态 |
|------|-------------|-------------|------|
| input_tokens | ✅ | ❌ 无 | 缺失 |
| output_tokens | ✅ | ❌ 无 | 缺失 |
| cache_read_tokens | ✅ | ❌ 无 | 缺失 |
| cache_write_tokens | ✅ | ❌ 无 | 缺失 |
| total_tokens | ✅ | ❌ 无 | 缺失 |
| estimated_cost_usd | ✅ | ❌ 无 | 缺失 |
| last_prompt_tokens | ✅ (压缩前检查) | ❌ 无 | 缺失 |
| memory_flushed | ✅ | ❌ 无 | 缺失 |

### 7. 异步支持

| 功能 | hermes-agent | MimirAether | 状态 |
|------|-------------|-------------|------|
| 异步SessionStore | ⚠️ 主要同步,部分异步 | ✅ 完全异步 | MimirAether更好 |
| 后台清理任务 | ✅ 通过has_active_processes | ✅ cleanup_loop | MimirAether更好 |
| 锁机制 | threading.Lock | asyncio.Lock | 架构差异 |

## 关键差距总结

### 高优先级缺失

1. **`SessionStore` (hermes) vs `SessionManager` (MimirAether)**
   - hermes: SQLite持久化 + 内存缓存 + JSONL兼容
   - MimirAether: 仅内存,重启丢失

2. **Reset策略评估**
   - hermes: idle/daily/both模式,支持per-platform/per-type覆盖
   - MimirAether: 仅TTL,无策略概念

3. **PII处理**
   - hermes: 完整hash机制,构建prompt时自动脱敏
   - MimirAether: 无

4. **Transcript管理**
   - hermes: append/rewrite/load完整功能
   - MimirAether: 无

5. **Token统计**
   - hermes: 完整统计用于成本跟踪和压缩决策
   - MimirAether: 无

### 架构差异

| 方面 | hermes-agent | MimirAether |
|------|-------------|-------------|
| 设计目标 | 生产级多会话管理 | 轻量级原型 |
| 持久化 | SQLite + JSONL | 仅内存 |
| 线程模型 | threading + 同步为主 | asyncio + 异步优先 |
| 配置 | GatewayConfig完整集成 | 独立TTL参数 |

## 建议

### Phase 1 (立即)
- 保留MimirAether的`SessionManager`作为基础
- 添加`SessionSource`和`SessionContext`数据结构
- 实现简单的`build_session_key()`

### Phase 2 (后续)
- 添加reset策略评估
- 添加PII处理辅助函数

### Phase 3 (最终)
- 添加transcript管理(可选,取决于需求)
- 如需持久化,参考hermes的SessionStore实现

## 依赖项

### hermes-agent 依赖
```
from .config import Platform, GatewayConfig, SessionResetPolicy, HomeChannel
from hermes_state import SessionDB  # SQLite
```

### MimirAether 依赖
```
from .message import Message  # 已有
```

---
*分析时间: 2026-04-27*
