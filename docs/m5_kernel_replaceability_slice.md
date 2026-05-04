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
- **断点续传端口**：`agent/checkpoint_port.py` 声明 **`CheckpointPersistencePort`**（`load_checkpoint` / `save_checkpoint` / `clear_checkpoint`）；``run_conversation`` 内一律使用 **`checkpoint_backend`**（默认 **`_BuiltinCheckpointBackend`** → 全局 ``get_checkpoint_manager()``）。  
  - **CLI**：`cli.run_task(..., checkpoint_backend=…)`。  
  - **API**：`api_service.AgentManager.set_checkpoint_backend_override(backend)`。  
  - **Agent**：`checkpoint_backend=`、`set_checkpoint_backend`。  
  - 测试：`agent/test_m5_checkpoint_port_slice.py`、`agent/test_m5_entry_checkpoint_injection_slice.py`。  
- **打包注入**：`agent/kernel_overrides.py` 中 **`AgentKernelOverrides`**；`MimirAetherAgent(..., kernel_overrides=…)` 与单字段二选一合并时，**显式单字段优先**。  
  - **CLI**：`cli.run_task(..., kernel_overrides=…)`；各 `*_backend` 等显式参数再覆盖 bundle 同名字段。  
  - **API**：`api_service.AgentManager.set_kernel_overrides(bundle)` 先于单字段 `set_*_override` 应用，**后者覆盖前者**。  
  - 测试：`agent/test_m5_kernel_bundle_slice.py`。  
- **Gateway SQLite 注入**：`gateway.run.GatewayRunner(..., session_db_factory=…)` 接受与 **`SessionDbClientFactory`** 相同的 **`create_session_db()`** 协议；用于替换网关侧 SessionDB 实例（`/title`、`/branch`、`AIAgent(session_db=)`、`/insights` 在已有 `_session_db` 时复用且不再 ``close`` 共享连接）。  
  - **JSONL ↔ SQLite 双写**：`gateway.session.SessionStore(..., transcript_session_db=…)`；网关启动时将 **`GatewayRunner._session_db`** 传入，使 **`append_to_transcript`** 在 **`skip_db=False`** 时除 JSONL 外调用 **`SessionDB.append_message`**（与 Hermes 消息表对齐）。**`skip_db=True`**（如 agent 已写入 SQLite）仍只写 JSONL。  
  - 测试：`agent/test_m5_gateway_session_db_slice.py`。  
- **``rewrite_transcript`` SQLite**：在存在 ``transcript_session_db`` 且实现 ``clear_messages(session_id)`` 时，先清空再按行 ``append_message`` 重放（与 JSONL 覆盖一致）；无 ``clear_messages`` 时仅写 JSONL，避免重复追加。  
- **之后**（可选）：为仅实现 append 的自定义后端提供显式 ``replace_transcript`` 协议，或对接非 Hermes 存储的删除语义。

## 自动化验收（无网）

```bash
python3 -m pytest -q agent/test_m5_kernel_replaceability_slice.py agent/test_m5_tool_port_slice.py agent/test_m5_entry_tool_injection_slice.py agent/test_m5_session_restore_port_slice.py agent/test_m5_entry_session_injection_slice.py agent/test_m5_session_db_factory_slice.py agent/test_m5_checkpoint_port_slice.py agent/test_m5_entry_checkpoint_injection_slice.py agent/test_m5_kernel_bundle_slice.py agent/test_m5_gateway_session_db_slice.py
```

纳入：`./run_ralph_tier0.sh`（Gate2）。

## 非目标（本切片不做）

- 不重写 `core_loop` 依赖注入、不迁移工具 registry / 会话存储（里程碑中的「例如」留待后续切片）。
- 不新增对外 API 或改变 CLI / API 契约。

## 修订

| 日期 | 说明 |
|------|------|
| 2026-05-04 | `rewrite_transcript`：`clear_messages` + 重放 `append_message`；无 `clear_messages` 则跳过 SQLite。 |
| 2026-05-04 | `SessionStore(transcript_session_db=)` + `append_to_transcript` SQLite 双写；`GatewayRunner` 先初始化 `_session_db` 再挂入 SessionStore。 |
| 2026-05-04 | `GatewayRunner(session_db_factory=)` → `SessionDbClientFactory`；`/insights` 复用 `_session_db`；`test_m5_gateway_session_db_slice`。 |
| 2026-05-04 | `AgentKernelOverrides`；`kernel_overrides=` / `set_kernel_overrides` / CLI `kernel_overrides`；`test_m5_kernel_bundle_slice`。 |
| 2026-05-03 | `CheckpointPersistencePort`；`run_conversation` 检查点；CLI/API 注入；相关测试。 |
| 2026-05-02 | `SessionDbClientFactory`；与 Insights + builtin restore 共用；`test_m5_session_db_factory_slice`；CLI/API/kw 注入。 |
| 2026-05-02 | `SessionRestorePort`；`session_backend` / `set_session_backend`；CLI/API 注入；`test_m5_session_restore_port_slice`、`test_m5_entry_session_injection_slice`。 |
| 2026-05-02 | `ToolInvocationPort`；`tool_backend` / `set_tool_backend`；CLI/API 注入；`test_m5_tool_port_slice`、`test_m5_entry_tool_injection_slice`。 |
| 2026-05-03 | CLI `run_task(..., llm_backend=…)`；`AgentManager.set_llm_backend_override`；`agent/test_m5_entry_llm_injection_slice.py`。 |
| 2026-05-03 | `MimirAetherAgent(llm_backend=…)` / `set_llm_backend`；默认 `_BuiltinLlmBackend` → `_builtin_call_model_with_tokens`。 |
| 2026-05-03 | 初版：`LlmInvocationPort` + 离线协议测试 + Gate2。 |
