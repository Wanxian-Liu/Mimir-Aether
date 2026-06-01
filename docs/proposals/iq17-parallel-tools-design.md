# IQ-41: 并行工具执行设计稿（仅设计）

> **状态**：设计稿（刘哥拍板 F=仅设计，不写生产并行）  
> **参考**：`agent/agent_loop.py` · `agent/async_bridge.py` · `agent/execution_pipeline.py`

## 1. 现状

Mimir 当前工具调用是**串行**的：

```
LLM → tool_call A → wait → result A → LLM → tool_call B → wait → result B
```

通过 `async_bridge.ThreadPoolExecutor`（单线程）实现。工具在 agent loop 中按顺序提交、等待、消费。

## 2. 哪些工具可以并行

### ✅ 只读（可并行，无污染）

| 工具 | 读什么 | 冲突风险 |
|------|--------|:--------:|
| `search_files` | 磁盘文件系统 | 🟢 无 |
| `read_file` | 磁盘文件内容 | 🟢 无 |
| `web_search` | 网络 | 🟢 无 |
| `web_extract` | 网络 | 🟢 无 |
| `browser_snapshot` | 浏览器 DOM | 🟡 共享浏览器上下文 |
| `browser_console` | 浏览器 JS 状态 | 🟡 同上 |
| `get_capsule_by_id` | SQLite 只读 | 🟢 无 |
| `list_capsules` | SQLite 只读 | 🟢 无 |
| `skills_list` | 文件系统 | 🟢 无 |
| `tool_search` | 文件系统 | 🟢 无 |
| `session_search` | SQLite | 🟢 无 |
| `vision_analyze` | 外部 API | 🟢 无（但成本可能高）|

### ❌ 有副作用（必须串行）

| 工具 | 副作用 | 冲突风险 |
|------|--------|:--------:|
| `write_file` | 写磁盘 | 🔴 覆盖 |
| `patch` | 写磁盘 | 🔴 冲突 |
| `terminal` | shell 进程 | 🔴 同 session 互扰 |
| `browser_click` | 浏览器状态 | 🔴 DOM 状态改变 |
| `browser_navigate` | 浏览器状态 | 🔴 导航打断 |
| `browser_type` | 浏览器表单 | 🔴 输入冲突 |
| `browser_press` | 浏览器按键 | 🔴 同上 |
| `browser_scroll` | 浏览器滚动 | 🟡 可并行但无意义 |
| `skill_manage` | 文件系统 | 🔴 写入冲突 |
| `cronjob` | SQLite + 进程 | 🔴 竞态 |
| `memory` | SQLite 写 | 🔴 写入冲突 |
| `send_message` | 网络 | 🔴 消息乱序 |
| `rl_*` | 训练状态 | 🔴 严重竞态 |
| `text_to_speech` | 文件系统 | 🟡 低风险 |

### ⚠️ 有条件（需要分组锁）

| 工具 | 条件 | 建议 |
|------|------|------|
| `browser_*` | 共享同一个 playwright context | 整个 browser 组一把锁 |
| `terminal(background=true)` | 不同 session_id 可并行 | 按 session_id 粒度加锁 |

## 3. 设计提案：双队列模型

```
[LLM 返回 N 个 tool_calls]
    ↓
[分类器：只读 vs 写]
    ↓
    只读队列 (parallel)          写队列 (serial)
    ┌─────┬─────┬─────┐         ┌─────┐
    │ t1  │ t2  │ t3  │  →      │ t4  │ → ...
    └─────┴─────┴─────┘         └─────┘
         ↓ wait all                 ↓
    [合并结果 → 按原始顺序重排 → 交给 LLM]
```

### 关键实现

```python
class ParallelToolDispatcher:
    def __init__(self):
        self._serial_lock = asyncio.Lock()  # 或 threading.Lock()
        self._read_only_tools = {"search_files", "read_file", "web_search", ...}
    
    async def dispatch_all(self, tool_calls: list) -> list:
        serial = [tc for tc in tool_calls if not self._is_read_only(tc)]
        parallel = [tc for tc in tool_calls if self._is_read_only(tc)]
        
        results = [None] * len(tool_calls)
        
        # 并行执行只读
        async def run_ro(ro_call):
            return await self._execute_one(ro_call)
        ro_results = await asyncio.gather(*[run_ro(tc) for tc in parallel])
        
        # 串行执行写
        for tc in serial:
            async with self._serial_lock:
                results[idx] = await self._execute_one(tc)
        
        # 按原始顺序合并
        return self._reorder(parallel_results, serial_results, original_indices)
```

### 和现有 agent_loop 的关系

当前 agent_loop 的循环是：

```python
for msg in llm_stream:
    if msg.tool_calls:
        for tc in msg.tool_calls:
            result = await tool_dispatcher(tc)
            results.append(result)
        messages.append(results)
```

改为：

```python
if msg.tool_calls:
    batch_results = await parallel_dispatcher.dispatch_all(msg.tool_calls)
    messages.append(batch_results)
```

## 4. 竞态清单

| # | 场景 | 风险 | 缓解 |
|---|------|:----:|------|
| 1 | 两个 `write_file` 写同一文件 | 🔴 | 串行队列确保顺序 |
| 2 | `read_file` + `write_file` 同一文件 | 🟡 | 写锁等读完成 |
| 3 | `terminal` 两个命令同一 session | 🔴 | `session_id` 粒度的锁 |
| 4 | `browser_navigate` + `browser_snapshot` | 🔴 | 整个 browser 组一把写锁 |
| 5 | `memory` 同 key replace + add | 🔴 | 串行队列 |
| 6 | `cronjob list` + `cronjob create` | 🟡 | read 拿共享锁，write 拿排他锁 |
| 7 | `rl_start_training` + `rl_get_results` | 🔴 | 写锁 |
| 8 | 只读工具超时阻塞整个 batch | 🟡 | 每个并行协程独立 timeout |

## 5. 实现建议

| 项 | 建议 |
|----|------|
| **实现者** | **Cursor**（本粒只出设计稿） |
| **文件** | `agent/parallel_dispatcher.py`（新文件） |
| **接入** | 在 `agent_loop.py` 中找到 `for tc in tool_calls` 的循环，替换为 `parallel_dispatcher.dispatch_all()` |
| **门控** | `MIMIR_PARALLEL_TOOLS=1`（默认 0） |
| **估计行数** | ~150 行（新文件）+ ~10 行（agent_loop 接入） |
| **测试** | mock tool_dispatcher，验证只读并发、写串行、顺序保持 |

## 6. 不做

- 并行 `terminal` 同一 session（只隔离 session_id
- 工具级优先级队列（所有工具等同）
- 动态并发限制（固定 `max_parallel=5`）
- 读缓存（tools 无 cached result，保持简单）
- rate limiting（归 gateway/provider 层）

## 7. 决策

| 问题 | 本设计推荐 |
|------|-----------|
| 默认开还是关？ | **关**（`MIMIR_PARALLEL_TOOLS=1` 启用） |
| 只读工具的分类名单硬编码还是配置？ | **硬编码**（代码内白名单，Mimir 没有配置注册表） |
| 超时策略？ | 只读工具继承原有 180s timeout；读超时当作常规 tool error |
| 日志？ | `dispatch_all` 前后各一条 log，含 parallel/serial 计数 |
