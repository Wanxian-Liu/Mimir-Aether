# Day 3: 状态管理 (hermes_state)

## 学习日期
2026-04-29

## 任务阶段
Week 1 - Day 3

---

## 阅读内容

### Hermes hermes_state.py (1238行)
- 文件: `hermes_state.py`
- 核心类: `SessionDB`
- 关键特性:
  - SQLite WAL模式（高并发读写）
  - FTS5全文搜索虚拟表
  - 随机退避重试机制
  - Schema版本迁移(v1→v6)
  - 会话压缩分裂(parent_session_id链)

### MimirAether hermes_state.py (1019行)
- 文件: `hermes_state.py`
- 核心类: `SessionDB`
- 与Hermes高度相似（99%代码复用）

---

## 关键发现

### 1. SQLite WAL模式设计

**Hermes核心设计**:
```python
# WAL模式：并发读取 + 单写入器
self._conn.execute("PRAGMA journal_mode=WAL")

# 随机jitter重试（避免WAL写锁竞争）
_WRITE_MAX_RETRIES = 15
_WRITE_RETRY_MIN_S = 0.020   # 20ms
_WRITE_RETRY_MAX_S = 0.150   # 150ms
```

**MimirAether**:
- ✅ 完全复制Hermes的WAL设计
- ✅ 相同的重试参数

### 2. FTS5全文搜索

**Hermes实现**:
```python
# FTS5虚拟表
CREATE VIRTUAL TABLE IF NOT EXISTS messages_fts USING fts5(
    content,
    content=messages,
    content_rowid=id
)

# 触发器保持同步
CREATE TRIGGER messages_fts_insert AFTER INSERT ON messages BEGIN
    INSERT INTO messages_fts(rowid, content) VALUES (new.id, new.content);
END;
```

**MimirAether**:
- ✅ 完全相同的FTS5实现

### 3. Schema演进

| Version | Hermes | MimirAether |
|---------|--------|-------------|
| v1 | 基础sessions + messages | ✅ 一致 |
| v2 | +finish_reason列 | ✅ 一致 |
| v3 | +title列 | ✅ 一致 |
| v4 | +唯一title索引 | ✅ 一致 |
| v5 | +billing相关列 | ✅ 一致 |
| v6 | +reasoning列 | ✅ 一致 |

**一致性**: 100%

### 4. 会话生命周期管理

**关键方法**:
- `create_session()`: 创建会话记录
- `end_session()`: 标记会话结束
- `reopen_session()`: 恢复已结束会话
- `append_message()`: 追加消息+更新计数器
- `get_messages_as_conversation()`: 加载为OpenAI格式

**MimirAether**:
- ✅ 完全一致的实现

### 5. FTS5查询清理

**Hermes的安全措施**:
```python
@staticmethod
def _sanitize_fts5_query(query: str) -> str:
    """防止FTS5语法错误和注入"""
    # 1. 保护配对引号
    # 2. 移除FTS5特殊字符
    # 3. 处理连字符/点号
    # 4. 移除悬空布尔运算符
```

**MimirAether**:
- ✅ 完全相同的实现

---

## 设计模式

### 1. 随机退避重试模式
```python
# Hermes: 避免WAL写锁竞争
jitter = random.uniform(_WRITE_RETRY_MIN_S, _WRITE_RETRY_MAX_S)
time.sleep(jitter)
```

### 2. Schema版本迁移模式
```python
# 增量迁移，保留现有数据
if current_version < 2:
    cursor.execute("ALTER TABLE messages ADD COLUMN finish_reason TEXT")
```

### 3. WAL检查点节流
```python
# 每50次写操作后尝试best-effort检查点
if self._write_count % _CHECKPOINT_EVERY_N_WRITES == 0:
    self._try_wal_checkpoint()
```

---

## MimirAether对比

| 功能 | Hermes | MimirAether | 差距 |
|------|--------|-------------|------|
| WAL模式 | ✅ | ✅ | 无 |
| FTS5搜索 | ✅ | ✅ | 无 |
| 随机退避重试 | ✅ | ✅ | 无 |
| Schema迁移 | v1→v6 | v1→v6 | 无 |
| 会话分裂 | ✅ | ✅ | 无 |
| 标题管理 | ✅ | ✅ | 无 |
| 消息导出 | ✅ | ✅ | 无 |
| 会话裁剪 | ✅ | ✅ | 无 |

**结论**: hermes_state模块是**100%对齐**的，MimirAether几乎完整复制了Hermes的SessionDB实现。

---

## 问题与思考

### Q1: 为什么MimirAether完整复制了hermes_state而不是重构?
A1: 可能原因:
- SessionDB是成熟稳定的实现
- SQLite + WAL + FTS5是经过验证的组合
- 复制比分阶段重构风险更低

### Q2: MimirAether是否真正使用了SessionDB?
A2: 需要验证。之前的分析显示MimirAether有独立的`agent/tool_registry.py` SQLite注册表，但hermes_state可能未被实际使用。

---

## 验证实验

### 实验1: 检查MimirAether的SessionDB是否被调用
```bash
grep -rn "SessionDB\|hermes_state" MimirAether/agent/*.py
```

### 实验2: 检查hermes_state的导入方式
```bash
grep -n "from hermes_state\|import hermes_state" hermes-agent/**/*.py
```

---

## 风险标记

✅ **hermes_state模块完全对齐Hermes**
⚠️ 需要验证MimirAether是否实际使用SessionDB

---

## 明日计划 (Day 4)

- [ ] 精读Hermes context_compressor.py (900行)
- [ ] 精读MimirAether context_compressor.py
- [ ] 分析压缩算法差异
- [ ] 验证压缩触发机制
