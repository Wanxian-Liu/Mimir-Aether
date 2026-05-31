# §20.3 勾选建议 — ADR-002-impl（解锁 ENGINE-P3W-01）

> **读者**：刘哥 · **日期**：2026-05-28  
> **状态**：**已拍板** 2026-05-28 · §20.3 **ADR-002-impl** `[x]`  
> **Cursor**：ENGINE-P3W-01 **已结案** · `engine-p3w-01-closeout.md`

---

## 拍什么板

批准 **Phase 2 最小 MemoryWriteFacade**（名称可微调），在 **ADR-001 / IND-05 单写者** 之上统一跨会话 **写入** 路由，**不**扩大 L1 全文注入、**不**改 L2/L3 只读预取默认。

| 路径 | 真源 | 现状 |
|------|------|------|
| **A · Capsules** | `$MIMIR_AETHER_HOME/memory/capsules/*.html` | `tools/mimircore_tool.py` 等 |
| **B · persistent 子段** | `$MIMIR_AETHER_HOME/data/persistent.json` | 已经 `agent/persistent_store.py`（IND-05） |
| **C · Wiki** | 人工 / 外部 | **不在 P3W-01 scope** |

**G-ADR-002 已勾**：顺序 L2 ✅ → L3 ✅ → **P3W**（本粒）→ 可选 capsule 入 Chroma（后续）。

---

## 拍板后 Cursor 交付（ENGINE-P3W-01）

1. **`MemoryWriteFacade`**（或等价）：`write_capsule(...)` / `write_persistent_patch(...)`；内部 B 只调 `persistent_store.read_modify_write` / `save_merged`。
2. **迁移表**：改前 call site 清单 → 全部经 Facade 或 documented allowlist。
3. **单测**：双写/丢 key 回归（扩 IND-05 或 `test_p3w_*`）。
4. **Contract + closeout**：`test_horizon_engine_p3w_01.py` · `engine-p3w-01-closeout.md` · tier0 · M6。

**预估迁移面（审计预览，非实施）**

| Call site | 段 | 经 persistent_store? |
|-----------|-----|----------------------|
| `agent/cross_session_memory.py` `save()` | memory/progress/… | ✅ `save_merged` |
| `agent/skill_curator.py` skill_usage / dormant | 子段 | ✅ `read_modify_write` |
| `tools/mimircore_tool.py` | capsules HTML | 独立路径 → Facade A |

**禁止（拍板后仍遵守）**：散落 `json.dump` 写 persistent · L1 全文注入 · 改 `SESSION_SEARCH_BACKEND` / `MIMIR_CROSS_SESSION_RAG` 生产默认 · WM Phase0。

---

## 不拍板的后果

- §20.1 **ENGINE-P3W-01** 保持 `[ ]`；下一工程粒 **ENGINE-GW-01** 文档总结案可并行，但 **Facade 全路径** 继续 deferred（ISSUES #3 语义不变）。

---

## 刘哥动作

在 `docs/MIMIR_EXEC_BACKLOG.md` **§20.3** 将 **ADR-002-impl** 改为 `[x]`（可附一行日期/授权语），并告知 Cursor「Gate 已过，做 ENGINE-P3W-01」。

**Gateway**：P3W-01 预期 **不必重启**（agent 写路径；无 gateway 默认行为变更）。
