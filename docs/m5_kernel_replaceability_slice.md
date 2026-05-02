# M5 最小切片：内核可替换（端口声明）

## 本 PR 范围

对应 **[M5：自研内核可替换](ralph_roadmap_milestones.md#m5自研内核可替换)** 的**第一步**：把「模型调用」从隐式方法提升为显式 **`LlmInvocationPort`**（`agent/llm_port.py`），与当前生产路径 **`MimirAetherAgent._call_model_with_tokens`**（`agent/core_loop.py`）在语义上对齐（返回 `(response_dict, latency_ms)`）。

- **今天**：`MimirAetherAgent` 构造参数 **`llm_backend`**（可选）与 **`set_llm_backend`**；默认 **`_BuiltinLlmBackend`** 委托 **`_builtin_call_model_with_tokens`**。  
  - **CLI**：`cli.run_task(..., llm_backend=…)`（`python cli.py -q` 不传，行为与旧版一致）。  
  - **API**：`api_service.AgentManager.set_llm_backend_override(backend)` 作用于**随后新创建**的 Agent（测试/定制；生产默认 `None`）。  
  - 垂直切片 **M3** 仍可用 **patch `_call_model_with_tokens`**；**M5 入口注入**见 `agent/test_m5_entry_llm_injection_slice.py`（不依赖该 patch）。
- **之后**：工具调度 / 会话存储等端口可继续按同模式扩展。

## 自动化验收（无网）

```bash
python3 -m pytest -q agent/test_m5_kernel_replaceability_slice.py
```

纳入：`./run_ralph_tier0.sh`（Gate2）。

## 非目标（本切片不做）

- 不重写 `core_loop` 依赖注入、不迁移工具 registry / 会话存储（里程碑中的「例如」留待后续切片）。
- 不新增对外 API 或改变 CLI / API 契约。

## 修订

| 日期 | 说明 |
|------|------|
| 2026-05-03 | CLI `run_task(..., llm_backend=…)`；`AgentManager.set_llm_backend_override`；`agent/test_m5_entry_llm_injection_slice.py`。 |
| 2026-05-03 | `MimirAetherAgent(llm_backend=…)` / `set_llm_backend`；默认 `_BuiltinLlmBackend` → `_builtin_call_model_with_tokens`。 |
| 2026-05-03 | 初版：`LlmInvocationPort` + 离线协议测试 + Gate2。 |
