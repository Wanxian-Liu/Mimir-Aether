# Mimir 工业级自学习 Playbook（EV-L 沉淀本）

> **读者**：Mimir（主写）、刘哥/Cursor（审阅）。  
> **真源队列**：`docs/MIMIR_EXEC_BACKLOG.md` **§2c**。  
> **规则**：每个 **EV-L** 只改**本文件**一处 + backlog §2c 勾 `[x]`；**禁止**改 `agent/`/`gateway/` 代码；可改 `docs/MIMIR_ISSUES.md`（每颗粒 ≤1 条）。

**写法模板（每节必填）**

```markdown
### 学到了（≤3 条）
- …

### 防再发（≤2 条，可执行）
- …

### 对标工业实践（1 句）
- 类似 …（K8s / Rails / SRE / …）因为 …
```

---

## 0. 对标总表（Mimir 填完 EV-L14 后核对）

| 工业级实践 | 典型框架/标准 | MimirAether 落点 | EV-L |
|------------|---------------|------------------|------|
| 合并前门禁 | CI required checks | `./run_ralph_tier0.sh` Gate1–3 | L01 L03 |
| 就绪探针 | K8s readiness/liveness | `pgrep gateway` + Lark wss + tool 冒烟 | L04 L10 |
| 故障安全 | Circuit breaker / fail-closed | `recovery_mixin` 不对代码错误 TRUNCATE | L05 L11 |
| 事后复盘 | Blameless postmortem | `MIMIR_INCIDENT_IR-20260520.md` | L02 L06 |
| 契约测试 | Consumer-driven contract | `ralph_parity_contract_v1` + tier0 映射 | L07 |
| 单写者状态 | DB transaction / ADR | `adr/001-persistent-single-writer` | L08 |
| 运行手册 | SRE runbook | `OPERATIONS_GATEWAY.md` + `restart_gateway_hard.sh` | L09 |
| 可观测性 | RED/USE metrics | d6 insights/monitor（缺口→E-006） | L13 |
| 真进化 vs 归档 | MLOps eval loop | `evolution_log` + 禁 `simulated` 存根 | L12 |

---

## 1. 三道门守门员清单（EV-L01 · 待写）

_（Mimir：读 `DEVELOPMENT_NORTH_STAR.md` §2–§5，写 5 条「冒烟前/改文档后/报完成前」自检）_

---

## 2. IR-20260520 事故教训（EV-L02 · 待写）

_（Mimir：读 `MIMIR_INCIDENT_IR-20260520.md`，写清：NameError 链 → TRUNCATE 放大 → 应用层 import 烟测）_

---

## 3. 变更门禁与 Ralph 节奏（EV-L03 · 待写）

_（Mimir：何时跑 1 次 tier0 vs 刘哥要求 3 连跑；触达 agent/gateway/tools 必跑）_

---

## 4. 拆分/重构后必跑烟测（EV-L04 · 待写）

_（Mimir：列出 `test_gateway_mixin_import_smoke.py`、`test_exec_mixin_imports.py`、`test_recovery_mixin_code_errors.py` 与 Gate1 import 的触发条件）_

---

## 5. Recovery：程序员错误 ≠ 上下文溢出（EV-L05 · 待写）

_（Mimir：读 `recovery_mixin` 护栏；列不可 TRUNCATE 异常类型 + 日志关键词）_

---

## 6. 红警 grep 集（EV-L06 · 待写）

_（Mimir：从 IR 提炼 ≥3 条 `grep -E`；注明「见红警即停手、记 ISSUES、@Cursor」）_

---

## 7. Parity 冒烟面（EV-L07 · 待写）

_（Mimir：从 `ralph_parity_contract_v1` 摘 3 个「gateway/agent 变更后必仍为真」的行为句 + 验证方式）_

---

## 8. 持久化单写者（EV-L08 · 待写）

_（Mimir：读 `adr/001-persistent-single-writer.md`；Mimir 永不 `git add data/persistent.json` 的原因 2 条）_

---

## 9. Gateway 运行 SOP（EV-L09 · 待写）

_（Mimir：浓缩 `OPERATIONS_GATEWAY` + `restart_gateway_hard.sh` 为 5 步卡片，供飞书转述刘哥）_

---

## 10. 重构后就绪清单（EV-L10 · 待写）

_（Mimir：对标 K8s readiness；≥8 条 checkbox：tier0、pgrep、TRUNCATE 基线、飞书 tool、无 Gateway stopped…）_

---

## 11. 升级矩阵：Mimir 拦 vs 交 Cursor（EV-L11 · 待写）

_（Mimir：表格列：症状 / Mimir 可做 / 必须 Cursor / 禁止伪修复如删 role=tool）_

---

## 12. 真进化 vs 伪进化（EV-L12 · 待写）

_（Mimir：结合 EV-M07；`evolution_log` 合格行 vs `simulated:true` 红线）_

---

## 13. 可观测缺口与 E-006（EV-L13 · 待写）

_（Mimir：结合 EV-M08；1 条 ISSUES + 1 条「E-006 做完后如何复验」）_

---

## 14. 本 Playbook 索引与复习节奏（EV-L14 · 待写）

_（Mimir：目录链接 §1–§13；建议每 **2 周** 或 **大改后** 复读 §4 §6 §10；飞书发「学习轨完成包」）_

---

## 附录 A — 学习轨完成包（模板）

```text
[Mimir 工业级学习轨] 2026-__-__
EV-L01..14: (勾选)
Playbook: docs/MIMIR_EV_L_INDUSTRIAL_LEARNING.md 已填 §_
最大收获 1 条:
防再发 1 条（最重要）:
建议工程: E-00x / 无
```
