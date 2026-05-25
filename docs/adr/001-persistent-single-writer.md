# ADR-001: persistent.json 单写者模式

> **状态**: Accepted (2026-05-25, IND-05)  
> **日期**: 2026-05-20  
> **来源**: ISSUES #4 | Session 72 截断事件 | d3 审计 P3-0

---

## 背景

`data/persistent.json` 是 MimirAether 的跨会话持久化文件，当前被两个模块独立写入：

| 写入者 | 文件 | 调用点 | 写入段 |
|--------|------|--------|--------|
| `CrossSessionMemory.save()` | `agent/cross_session_memory.py:167` | `core_loop.py:1928`（每次会话结束） | 全量（memory, progress, pending_tasks, last_session_end 等） |
| `_save_persistent()` | `agent/skill_curator.py:125` | L219（skill_usage）, L337（dormant_skills） | 全量（skill_usage / dormant_skills 子段变更） |

两者都遵循 **Read-Modify-Write** 模式：

```
_load_persistent()  →  修改内存 dict  →  _save_persistent()
```

## 问题

### 竞态条件 (Race Condition)

两个写入者之间无任何锁协调。时序如下即触发覆盖：

```
时间 ──────────────────────────────────────────►

CrossSessionMemory     _load_persistent()  ──→  modify  ──→  _save_persistent()
SkillCurator           _load_persistent()  ──→  modify  ──→  _save_persistent()
                                                              ↑
                                                    覆盖了 CrossSessionMemory
                                                    刚写入的变更
```

### Session 72 截断事件

这不是理论风险。Session 72 曾发生 `persistent.json` 被截断到 5 行（正常 324 行），根因链：

1. `skill_curator._load_persistent()` 因 JSON 解析异常返回 `{}`
2. 空 dict 通过 `_save_persistent()` 写回磁盘
3. CrossSessionMemory 的所有数据被覆盖

Session 73 已加写前校验（`_REQUIRED_TOP_KEYS` 门禁），**但双写竞态的结构性风险未消除**。

### 当前缓解措施（不充分）

| 措施 | 文件 | 有效？ |
|------|------|--------|
| 写前结构校验 (version/memory/progress) | skill_curator.py:134 | ✅ 防截断 |
| 原子写入 (tmp + rename) | skill_curator.py:118 | ✅ 防半写 |
| 写入前 .bak 备份 | skill_curator.py:147 | ⚠️ 非事务 |
| `_merge_disk_changes()` | cross_session_memory.py:186 | ⚠️ merge 前无锁，仍有窗口 |

**原子写入只保证单次写入的原子性，不保证 Read-Modify-Write 的原子性。**

## 决策

### 方案 A: 全局 asyncio.Lock（当前推荐）

在 `skill_curator.py` 模块级加一个 `asyncio.Lock`，所有写入路径获取同一把锁。

```python
# skill_curator.py
_write_lock = asyncio.Lock()

async def _save_persistent(data: dict) -> None:
    async with _write_lock:
        ...  # 现有逻辑不变

# cross_session_memory.py — save() 改为 async
async def save(self) -> bool:
    from agent.skill_curator import _write_lock
    async with _write_lock:
        ...  # 现有逻辑不变
```

**优点**: 改动小（~10 行），无新依赖，利用 asyncio 原生锁。
**缺点**: CrossSessionMemory.save() 需改为 async，调用方 `core_loop.py:1928` 需 `await`。

### 方案 B: 单写者收敛 — 所有写入走 CrossSessionMemory

SkillCurator 不再直接写 persistent.json，改为调用 CrossSessionMemory 的 segment API：

```python
# skill_curator 不再调 _save_persistent()
# 改为:
cross_memory.update_segment("skill_usage", data)
cross_memory.save()  # 唯一写入口
```

**优点**: 彻底消除竞态；语义清晰。
**缺点**: 改动较大；SkillCurator 需持有 CrossSessionMemory 引用。

### 方案 C: 文件级 fcntl 锁

```python
import fcntl
with open(PERSISTENT_PATH, 'r+') as f:
    fcntl.flock(f, fcntl.LOCK_EX)
    ...
```

**优点**: 不依赖 asyncio，跨进程安全。
**缺点**: 不兼容 temp+rename 原子模式（rename 后 fd 失效）；需要先读再写同一 fd。

## 建议

**采用方案 A**（全局 asyncio.Lock），理由：

1. 最小改动量，现有原子写入 + 写前校验全部保留
2. 当前两个写入者都运行在同一个 asyncio 事件循环内，asyncio.Lock 足够
3. 方案 B/C 可作为长期演进方向，但当前 d3 Sprint 优先拆 GOD Class

## 后果

- CrossSessionMemory.save() 签名由 `def save(self) -> bool` 变为 `async def save(self) -> bool`
- `core_loop.py:1928` 由 `self._cross_memory.save()` 变为 `await self._cross_memory.save()`
- 不再有静默覆盖风险

## 实施（IND-05）

**已采用方案 A 的同步等价物**：`agent/persistent_store.py` 模块级 `threading.Lock`，所有 RMW 经 `load` / `save` / `read_modify_write` / `save_merged`。

| 模块 | 变更 |
|------|------|
| `agent/persistent_store.py` | 新建：原子写、写前校验、`.bak`、锁 |
| `agent/skill_curator.py` | 经 `read_modify_write` 写 segment；路径对齐 `get_mimir_data_dir()` |
| `agent/cross_session_memory.py` | `save()` → `save_merged` + `merge_disk_into_memory` |

**测试**：`tests/agent/test_persistent_single_writer_ind05.py`（并发 segment 不丢）。

**未做**：asyncio.Lock（调用链均为同步）；方案 B 单入口收敛可后续演进。
