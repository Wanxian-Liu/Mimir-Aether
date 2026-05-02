# M5 最小切片：内核可替换（端口声明）

## 本 PR 范围

对应 **[M5：自研内核可替换](ralph_roadmap_milestones.md#m5自研内核可替换)** 的**第一步**：把「模型调用」从隐式方法提升为显式 **`LlmInvocationPort`**（`agent/llm_port.py`），与当前生产路径 **`MimirAetherAgent._call_model_with_tokens`**（`agent/core_loop.py`）在语义上对齐（返回 `(response_dict, latency_ms)`）。

- **今天**：`MimirAetherAgent` 构造参数 **`llm_backend`**（可选）与 **`set_llm_backend`**；默认 **`_BuiltinLlmBackend`** 委托 **`_builtin_call_model_with_tokens`**。  
  - **CLI**：`cli.run_task(..., llm_backend=…)`（`python cli.py -q` 不传，行为与旧版一致）。  
  - **API**：`api_service.AgentManager.set_llm_backend_override(backend)` 作用于**随后新创建**的 Agent（测试/定制；生产默认 `None`）。  
  - 垂直切片 **M3** 仍可用 **patch `_call_model_with_tokens`**；**M5 入口注入**见 `agent/test_m5_entry_llm_injection_slice.py`（不依赖该 patch）。
- **工具批处理端口**：`agent/tool_port.py` 声明 **`ToolInvocationPort`**；`_execute_tools` → **`tool_backend`**（默认 **`_BuiltinToolBackend`** → **`_builtin_execute_tools`**，语义与原先 `_execute_tools` 体一致）。  
  - **CLI**：`cli.run_task(..., tool_backend=…)`。  
  - **API**：`api_service.AgentManager.set_tool_backend_override(backend)`。  
  - 测试：`agent/test_m5_tool_port_slice.py`、`agent/test_m5_entry_tool_injection_slice.py`。
- **会话恢复端口**：`agent/session_port.py` 声明 **`SessionRestorePort`**（`restore_after_init`）；`_restore_session` → **`session_backend`**（默认 **`_BuiltinSessionRestore`** → **`_builtin_restore_session`**，与原先 SessionDB 恢复体一致）。  
  - **CLI**：`cli.run_task(..., session_backend=…)`。  
  - **API**：`api_service.AgentManager.set_session_backend_override(backend)`。  
  - 测试：`agent/test_m5_session_restore_port_slice.py`、`agent/test_m5_entry_session_injection_slice.py`。  
- **SessionDB 工厂**：`SessionDbClientFactory`（`create_session_db`）统一 **InsightsEngine(SQL)** 与 **`_builtin_restore_session`** 的客户端构造；默认 **`_BuiltinSessionDbFactory`**（等价于原「`SessionDB is not None` 则 `SessionDB()`」）。  
  - **CLI**：`cli.run_task(..., session_db_factory=…)`。  
  - **API**：`api_service.AgentManager.set_session_db_factory_override(factory)`。  
  - **Agent**：`session_db_factory=`、`set_session_db_factory`（已构造的 ``insights`` 不自动重建）。  
  - 测试：`agent/test_m5_session_db_factory_slice.py`；入口_kw/API 见 `agent/test_m5_entry_session_injection_slice.py` 后半。  
- **之后**：可选将会话写入路径也纳入端口（若与 Hermes 写入语义对齐有里程碑要求）。

## 自动化验收（无网）

```bash
python3 -m pytest -q agent/test_m5_kernel_replaceability_slice.py agent/test_m5_tool_port_slice.py agent/test_m5_entry_tool_injection_slice.py agent/test_m5_session_restore_port_slice.py agent/test_m5_entry_session_injection_slice.py agent/test_m5_session_db_factory_slice.py
```

纳入：`./run_ralph_tier0.sh`（Gate2）。

## 非目标（本切片不做）

- 不重写 `core_loop` 依赖注入、不迁移工具 registry / 会话存储（里程碑中的「例如」留待后续切片）。
- 不新增对外 API 或改变 CLI / API 契约。

## 修订

| 日期 | 说明 |
|------|------|
| 2026-05-02 | `SessionDbClientFactory`；与 Insights + builtin restore 共用；`test_m5_session_db_factory_slice`；CLI/API/kw 注入。 |
| 2026-05-02 | `SessionRestorePort`；`session_backend` / `set_session_backend`；CLI/API 注入；`test_m5_session_restore_port_slice`、`test_m5_entry_session_injection_slice`。 |
| 2026-05-02 | `ToolInvocationPort`；`tool_backend` / `set_tool_backend`；CLI/API 注入；`test_m5_tool_port_slice`、`test_m5_entry_tool_injection_slice`。 |
| 2026-05-03 | CLI `run_task(..., llm_backend=…)`；`AgentManager.set_llm_backend_override`；`agent/test_m5_entry_llm_injection_slice.py`。 |
| 2026-05-03 | `MimirAetherAgent(llm_backend=…)` / `set_llm_backend`；默认 `_BuiltinLlmBackend` → `_builtin_call_model_with_tokens`。 |
| 2026-05-03 | 初版：`LlmInvocationPort` + 离线协议测试 + Gate2。 |
