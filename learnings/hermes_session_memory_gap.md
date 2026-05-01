# Hermes vs MimirAether: Session & Memory 架构对比

> 第3小节 · 2026-04-29  
> 对比对象: Hermes Agent `hermes_state.py`(1238行) + `agent/memory_provider.py` + `agent/memory_manager.py` + `gateway/session.py` + `tools/session_search_tool.py`  
> vs MimirAether `agent/session_manager.py`(243行) + `agent/session_tracker.py` + `agent/memory_system.py`(498行) + `agent/memory_manager.py`(387行) + `agent/memory_fence.py`(514行)

---

## 一、Hermes 设计亮点 (5个)

### 1. SQLite + FTS5 全量会话存储 (`hermes_state.py`)

Hermes的`SessionDB`是**工业级SQLite实现**，远超简单的kv存储：

- **WAL模式**：支持多进程并发读（gateway多平台共享一个`state.db`）
- **FTS5全文搜索**：`messages_fts`虚拟表 + INSERT/UPDATE/DELETE触发器自动同步
- **完整消息存储**：每条消息存储 role, content, tool_calls, tool_name, timestamp, token_count, finish_reason, reasoning, reasoning_details
- **应用层写锁重试**：随机jitter(20-150ms)替代SQLite内置确定性退避，避免网关高并发下的convoy效应
- **Schema迁移链**：`SCHEMA_VERSION` 1→6，每步可追溯
- **Billing全字段**：estimated_cost_usd, actual_cost_usd, billing_provider, billing_mode, pricing_version, cost_status, cost_source
- **压缩触发会话链**：`parent_session_id` 链接父子会话

### 2. 可插拔MemoryProvider架构 (`agent/memory_provider.py`)

精心设计的抽象基类，生命周期完整：

```
initialize() → system_prompt_block() → prefetch() → sync_turn() → shutdown()
     ↑                                                        ↓
  on_turn_start()  on_pre_compress()  on_session_end()  on_delegation()  on_memory_write()
```

- **7个外部Provider**：Honcho, Hindsight, Mem0, OpenViking, Byterover, Supermemory, RetainDB + Holographic
- **单外部Provider限制**：只允许1个外部provider激活，防止工具schema膨胀
- **内置Provider不可移除**：BuiltinMemoryProvider (MEMORY.md/USER.md) 始终激活
- **Config发现机制**：`get_config_schema()` 驱动 `hermes memory setup` 向导
- **Provider间故障隔离**：一个provider失败不阻塞其他

### 3. MemoryManager 编排器 (`agent/memory_manager.py`)

单点集成到`run_agent.py`，零侵入：

- **Context Fencing**：`<memory-context>`标签包裹预取记忆，明确标记为系统背景数据
- **工具路由**：`tool_name → MemoryProvider` 索引自动分发
- **生命周期批量操作**：`initialize_all()`, `sync_all()`, `prefetch_all()`, `shutdown_all()`
- **压缩前提取**：`on_pre_compress()` 在上下文压缩前从即将丢弃的消息中提取洞见

### 4. 多平台Session Store + 重置策略 (`gateway/session.py`)

- **确定性Session Key生成**：`agent:main:{platform}:{chat_type}:{chat_id}:{thread_id}:{user_id}`
- **重置策略矩阵**：idle(空闲超时)、daily(每日重置)、both、none，按平台/会话类型可配置
- **自动重置前flush**：过期会话在重建前先完成memory写入
- **PII脱敏**：`_PII_SAFE_PLATFORMS` 白名单，对WhatsApp/Signal/Telegram进行ID哈希
- **/stop挂起机制**：`suspended`标志防止重启后恢复卡住的会话

### 5. 跨会话FTS5搜索 + LLM摘要 (`tools/session_search_tool.py`)

- **双模式**：空查询→列出最近会话(零LLM成本)；关键词→FTS5搜索+摘要
- **智能截断**：在匹配位置附近截取~100K字符窗口
- **并行摘要**：多个匹配会话并发调用廉价模型(Gemini Flash)总结
- **父子会话解析**：自动沿`parent_session_id`链找到根会话，排除当前活跃会话
- **隐藏源过滤**：排除`tool`源(第三方集成)避免污染历史

---

## 二、MimirAether 差距列表

### P0 — 严重缺失 (阻断级)

#### 1. ❌ 无消息存储表

**Hermes**: `messages`表存储每条消息(role, content, tool_calls, tool_name, timestamp, token_count, finish_reason, reasoning)
**MimirAether**: `SessionManager`只有`sessions`/`checkpoints`/`events`表。`session_tracker.py`有`session_events`表但只存metadata。**没有任何地方存储完整的对话消息**。

```sql
-- Hermes messages表 (缺失)
CREATE TABLE messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL REFERENCES sessions(id),
    role TEXT NOT NULL,
    content TEXT,
    tool_call_id TEXT,
    tool_calls TEXT,
    tool_name TEXT,
    timestamp REAL NOT NULL,
    token_count INTEGER,
    finish_reason TEXT,
    reasoning TEXT,
    reasoning_details TEXT
);
```

**修复**: 在`SessionManager`中添加`messages`表，在`agent_loop`中每轮调用`save_message()`

#### 2. ❌ 无FTS5全文搜索

**Hermes**: FTS5虚拟表 + 触发器自动同步，`search_messages()`支持布尔查询、角色过滤、源过滤
**MimirAether**: 只有`search()`方法做`LIKE '%keyword%'`查询，无全文索引

**修复**: 
```sql
CREATE VIRTUAL TABLE messages_fts USING fts5(content, content=messages, content_rowid=id);
CREATE TRIGGER messages_fts_insert AFTER INSERT ON messages BEGIN
    INSERT INTO messages_fts(rowid, content) VALUES (new.id, new.content);
END;
```

#### 3. ❌ MemorySystem 与 MemoryManager 重复未集成

**MimirAether有两个独立系统**：
- `MemorySystem` (498行): 键值存储，带关系图(`memory_relations`)、历史追踪(`memory_history`)、TTL、重要性评分、老化整合
- `MemoryManager` (387行): 从Hermes复制过来的Provider架构，定义了`MemoryProvider`抽象类和`BuiltinMemoryProvider`

**问题**: 它们不通信。`MemorySystem`是独立DB，`MemoryManager`定义provider但不连接到`MemorySystem`。Hermes的设计是`MemoryManager`编排`MemoryProvider`实现，而每个provider自己管理后端。

**修复**: 将`MemorySystem`重构为`MemoryProvider`的一个实现（如`MimirMemoryProvider`），由`MemoryManager`编排。或者废弃`MemoryManager`，让`MemorySystem`直接实现`MemoryProvider`接口。

### P1 — 高优先级

#### 4. ❌ MemoryProvider只有骨架

**Hermes**: 7个外部provider + 1个内置provider（完整实现在`tools/memory_tool.py`的`MemoryStore`类）
**MimirAether**: `BuiltinMemoryProvider`只有54行骨架（只读MEMORY.md/USER.md，无写操作、无去重、无锁定），无外部provider

**修复**:
1. 补充`BuiltinMemoryProvider`完整实现（参考Hermes的`MemoryStore`：§分隔符、文件锁、原子写入、安全扫描、字符限制）
2. 集成至少1个外部provider（推荐Mem0或Honcho）

#### 5. ❌ 无Session重置策略

**Hermes**: idle超时(minutes)/daily(at_hour)/both/none 四种策略，按平台和会话类型可配置
**MimirAether**: 只有`active=0`软删除，无自动过期

**修复**: 在`SessionManager`中添加：
```python
class ResetPolicy:
    mode: str  # "idle", "daily", "both", "none"
    idle_minutes: int
    at_hour: int

def should_reset(self, session_id: str, policy: ResetPolicy) -> Optional[str]:
    """Returns reset_reason or None"""
```

#### 6. ❌ 无跨会话搜索工具

**Hermes**: `session_search`工具→FTS5搜索→LLM摘要→结构化返回
**MimirAether**: 无此工具，无法让agent回顾过去的对话

**修复**: 在FTS5就位后实现`session_search`工具，包含：
- FTS5查询匹配消息
- 按会话分组取top-N
- 调用辅助模型(Gemini Flash)做聚焦摘要
- 并行执行多个会话的摘要

### P2 — 中优先级

#### 7. ⚠️ Token/Cost追踪不完整

**Hermes**: 12个billing相关字段，支持绝对/增量两种更新模式
**MimirAether**: SessionTracker有基础字段(`input_tokens`, `output_tokens`, `estimated_cost_usd`)，但缺少：`billing_provider`, `billing_base_url`, `billing_mode`, `actual_cost_usd`, `cost_status`, `cost_source`, `pricing_version`, `cache_read_tokens`, `cache_write_tokens`, `reasoning_tokens`

**修复**: 
1. 对齐SessionTracker的sessions表字段
2. 添加`update_token_counts()`方法，支持绝对/增量模式

#### 8. ⚠️ 无压缩触发会话分裂

**Hermes**: `parent_session_id`链接压缩产生的子会话
**MimirAether**: sessions表无`parent_session_id`字段

**修复**: 添加`parent_session_id`字段和`FOREIGN KEY`引用

#### 9. ⚠️ ContextEngine未集成到Session生命周期

**Hermes**: `ContextEngine.on_session_start/end()`由会话生命周期调用
**MimirAether**: `SessionManager`和上下文压缩器是两条平行线，不互通

**修复**: 在`SessionManager.create_session()`时调用`ContextEngine.on_session_start()`，在结束/重置时调用`on_session_end()`

### P3 — 低优先级

#### 10. 🔧 围栏工具重复

`memory_fence.py`的`sanitize_context`/`build_memory_context_block`与`memory_manager.py`中的近重复（`memory_fence.py`用的是```regex```模式，`memory_manager.py`用的是`<memory-context>`标签模式，后者是Hermes的正确版本）。

**修复**: 删除`memory_fence.py`中的重复，统一使用`memory_manager.py`的版本。

#### 11. 🔧 无Schema版本控制

**Hermes**: `SCHEMA_VERSION` + 迁移链(v1→v6)
**MimirAether**: 直接在`_migrate_token_fields()`中ALTER TABLE，无版本号追踪

**修复**: 添加`schema_version`表 + 结构化迁移系统。

---

## 三、架构修复路线图

```
Phase 1 (1周) — P0修复
├─ 1. SessionManager添加messages表 + save_message()
├─ 2. 添加FTS5虚拟表和触发器
└─ 3. MemorySystem重构为MemoryProvider实现，由MemoryManager编排

Phase 2 (1周) — P1修复
├─ 4. BuiltinMemoryProvider完整实现(对齐Hermes MemoryStore)
├─ 5. 添加ResetPolicy框架 + auto_reset逻辑
└─ 6. 实现session_search工具

Phase 3 (1周) — P2补全
├─ 7. Billing字段对齐
├─ 8. parent_session_id + 压缩分裂
└─ 9. ContextEngine → SessionManager生命周期绑定

Phase 4 (1周) — P3清理
├─ 10. 统一fence工具
└─ 11. Schema版本化
```

---

## 四、关键文件对照表

| 功能 | Hermes | MimirAether | 差距 |
|------|--------|-------------|------|
| 会话持久化 | `hermes_state.py` SessionDB (1238行) | `session_manager.py` (243行) | 缺消息表/FTS5/迁移 |
| 会话管理 | `gateway/session.py` SessionStore (476行) | `session_manager.py` | 缺重置策略/PII脱敏 |
| 状态追踪 | SessionDB (内聚) | `session_tracker.py` (280行，独立) | 字段不完整 |
| 记忆抽象 | `agent/memory_provider.py` (220行) | `agent/memory_manager.py` MemoryProvider | 基本对齐 |
| 记忆编排 | `agent/memory_manager.py` (270行) | `agent/memory_manager.py` MemoryManager | 基本对齐 |
| 记忆实现 | `tools/memory_tool.py` MemoryStore (440行) | `agent/memory_system.py` (498行，独立) | 两套不集成 |
| 内置Provider | BuiltinMemoryProvider (实际) | BuiltinMemoryProvider (54行骨架) | 功能缺失 |
| 外部Provider | 7个 (Honcho/Mem0/Hindsight/...) | 0个 | 完全缺失 |
| 跨会话搜索 | `tools/session_search_tool.py` (330行) | 无 | 完全缺失 |
| 围栏安全 | 内建在`memory_tool.py` | `memory_fence.py` (514行) | 重复/不协调 |
| Schema版本 | v1→v6迁移链 | 无 | 缺失 |

---

## 五、核心设计原则提取 (从Hermes学习)

1. **消息是资产的根源** — 不存消息就没法搜索、没法摘要、没法回忆。`messages`表是所有高级功能的基础。
2. **搜索先于AI** — FTS5轻量级全文搜索是session_search、session_browse等项目的基础，不需要embedding/向量。
3. **Provider编排优于独立系统** — `MemoryManager`编排`MemoryProvider`实现，每个provider管理自己的后端，清晰的边界和故障隔离。
4. **冻结快照模式** — 会话开始时冻结系统提示词的memory快照，中会话写入更新磁盘但不刷新提示词，保护prefix cache。
5. **压缩≠丢弃** — 压缩产生子会话（parent_session_id链），不会丢失历史，仍可搜索和回顾。
