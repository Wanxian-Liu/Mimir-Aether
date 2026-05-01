
## 6. MimirAether独有优势

| 功能 | 说明 |
|------|------|
| ✅ WebSocket `/ws` | Hermes没有WebSocket支持，这是Mimir的优势 |
| ✅ AgentManager单例 | 简洁的agent生命周期管理，适合单进程场景 |
| ✅ 模型列表硬编码 | 简单直接，对少数模型场景够用 |

---

## 7. 修正路线图

### 阶段1: 安全加固 (先修命门)
1. 实现`_check_auth()` — Bearer token + hmac.compare_digest
2. 添加`security_headers_middleware`
3. 添加`body_limit_middleware`
4. 端口冲突检测 + 网络暴露检查

### 阶段2: 核心协议对齐
5. 实现`/v1/responses`端点 (POST/GET/DELETE)
6. 实现`ResponseStore` (SQLite + LRU)
7. 实现`/v1/runs/{id}/events` SSE流
8. 修复会话连续性 (SessionDB集成)
9. 完善流式响应 (queue + keepalive + 断连处理)

### 阶段3: 生产加固
10. CORS中间件
11. 幂等性支持
12. 线程隔离 (`run_in_executor`)
13. 对话历史完整管理
14. 并发限制 + 孤儿清理

### 阶段4: 增值功能
15. `/api/jobs` cron管理API
16. 工具进度SSE事件 (`hermes.tool.progress`)
17. 动态模型名解析

---

## 8. 代码片段速查

### Hermes确定性Session ID
```python
def _derive_chat_session_id(system_prompt, first_user_message):
    seed = f"{system_prompt or ''}\n{first_user_message}"
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16]
    return f"api-{digest}"
```

### Hermes ResponseStore核心
```python
class ResponseStore:
    # SQLite + WAL
    CREATE TABLE responses (response_id TEXT PRIMARY KEY, data TEXT, accessed_at REAL)
    CREATE TABLE conversations (name TEXT PRIMARY KEY, response_id TEXT)
    # LRU: DELETE ... ORDER BY accessed_at ASC LIMIT N
```

### Hermes Idempotency
```python
_idem_cache = _IdempotencyCache(max_items=1000, ttl_seconds=300)
fp = _make_request_fingerprint(body, keys=["model", "messages", ...])
result = await _idem_cache.get_or_set(key, fp, compute_coro)
```

### Hermes工具进度SSE (防幻觉 #6972)
```python
# 发送时
event: hermes.tool.progress
data: {"tool": "list", "emoji": "⏰", "label": "列出文件"}

# 客户端: 自定义事件类型不存入对话历史
# 不会导致模型"学会"输出emoji标记
```

---

## 9. 关键常量速查

| 常量 | Hermes | MimirAether |
|------|--------|-------------|
| 默认端口 | 8642 | 18999 |
| 默认host | 127.0.0.1 | 0.0.0.0 |
| max_request_bytes | 1MB | 1MB |
| max_content_length | 64KB | 64KB |
| max_stored_responses | 100 | 100 |
| sse_keepalive | 30s | 无 |
| max_concurrent_runs | 10 | 无限制 |
| run_stream_ttl | 300s | 无 |

---

## 10. 总结

| 分类 | 数量 |
|------|------|
| ❌ 完全缺失 | 19项 |
| ⚠️ 部分实现 | 4项 |
| ✅ 已对齐 | 2项 |
| 🔷 Mimir独有 | 1项 (WebSocket) |

**核心结论**: MimirAether的`api_service.py`是Hermes `api_server.py`的进一步简化版 — 缺少认证、持久化、事件流、幂等性、会话连续性等关键生产功能。虽然基础端点可用，但不适合暴露到网络或用于多轮复杂交互。

**推荐策略**: 不是"追赶Hermes 100%"，而是选择性吸收 — 先拿安全+状态管理，再按需加增值功能。WebSocket是Mimir的相对优势，可以保留并深化。
