# 独立学习：Gateway SessionStore 与 transcript 双写

| 字段 | 值 |
|------|-----|
| 日期 | 2026-05-04 |
| 里程碑 | C（阶段 3） |
| 主文件 | `gateway/session.py`（**SessionStore**） |
| 相关工程切片 | [m5_kernel_replaceability_slice.md](../m5_kernel_replaceability_slice.md) |

---

## 1. 范围与非目标

**范围**

- **JSONL** 每会话 transcript 文件路径与 **append** 语义。
- 可选 **`transcript_session_db`**：与 **SQLite** 的 **dual-write**（`append_to_transcript`、`rewrite_transcript`）。
- **`skip_db`**：agent 已写 SQLite 时仅 JSONL 的路径（与 M5 文档一致）。

**非目标**

- 不覆盖所有 gateway HTTP 路由；不读 `gateway/run.py` 全量。

---

## 2. 架构要点

- **`SessionStore.append_to_transcript(session_id, message, skip_db=False)`**：先追加 JSONL，再在 `_db` 存在且非 `skip_db` 时 **`_append_transcript_dict_to_session_db`**。
- **`rewrite_transcript`**：整文件重写 JSONL + 可选批量刷 DB（与 append 对称）。
- **与 GatewayRunner**：`GatewayRunner` 将 **`_session_db`** 注入 **`SessionStore`**，使网关与 agent 共享 Hermes 对齐的 **SessionDB**（见 M5 文档）。

**数据流（ASCII）**

```
HTTP / runner → SessionStore.append_to_transcript
                     ├→ JSONL file (always)
                     └→ SessionDB.append_message (if _db and not skip_db)
```

---

## 3. 与 Hermes / Parity

- 行为上对齐「Hermes 消息表 + 传统 JSONL」双轨；差异在部署是否挂载 **`transcript_session_db`**。
- 回归证据：M5 相关测试与 **`./run_ralph_tier0.sh`**（非本报告逐条展开）。

---

## 4. 差距与改进建议

1. **可观测性**：双写失败时当前多为 debug log；运维可约定指标或告警门槛（另 issue）。
2. **文档**：在 **`docs/m3_api_chat_slice.md`** 或 API 读者路径加一句「transcript 落盘与 DB 的时序」指回 **`gateway/session.py`**。

---

## 5. 拟迁移项

- 本批将 **`phase_c_studies/README.md`** 入链；可选后续 PR 补 API 文档一句。

---

## 6. 复盘

- **学到什么**：**`skip_db=True`** 是避免双写竞态的显式契约，合并 agent/gateway 改动时必须保留语义。
- **下一步**：若引入新存储后端，应走 **M5** 的 `session_db_factory` 而非直改 JSONL 格式。
- **风险**：`rewrite_transcript` 与并发 append 的竞态需继续依赖上层串行化或锁（已有实践以代码为准）。
