# d1–d7 Wiki 审计评注（对照真源 · 不改正文）

> **目的**：刘哥离线时留下的**知识与经验层**。  
> **原文**（只读、不编辑）：`~/.openclaw/wiki/main/iterations/d{1..7}-audit-report.html`  
> **真源**：本仓库代码 + `~/.mimiraether` 运行时 + `docs/MIMIR_EXEC_BACKLOG.md`  
> **评注基线**：2026-05-20 · `main` @ `77ade10`（E-002/E-003 mixin split 已 commit）

---

## 如何使用本文

| 读者 | 用法 |
|------|------|
| **刘哥** | 看每节「结论一句」+「仍值得做的 TOP3」；不必重读 HTML |
| **Cursor 工程** | 排 E-004～E-009 时，用「现状核对」避免重复已合工作 |
| **Mimir** | 练「审计 vs 真源」：读 HTML 一条 → 在仓库 `grep`/日志验证 → 写 ISSUES |

**原则**：旧 HTML 是**当时认知的快照**，不少条目**过度悲观、重复计数、或未跟踪合入**；直接改 HTML 会掩盖历史。真改进写在 **ISSUES / backlog / 代码 / 本文**。

---

## 跨阶段总评

| 维度 | Wiki 审计习惯 | 2026-05-20 实况 | 建议 |
|------|----------------|-----------------|------|
| **估时** | d1–d3 累计 ~100h | 大量 P0 已合 main；剩余集中在 d5–d7 | 新排期用 **E-*** 队列，勿照搬 HTML 工时 |
| **误报** | d1 Review 83% 误报、d3 33% | 说明「多角色评审」未绑 tier0/冒烟 | 以后审计：**一条 finding = 一条可执行验证命令** |
| **与 Mimir 分工** | 混在「ENG 任务」里 | Mimir 已做 d1–d3 大部分验证 | 训练任务见 `MIMIR_D17_AUDIT_AND_TASKS.md` T-* |
| **最高分误区** | d4 架构 8/10 | 拆分后 `core_loop` 仍 ~1295 行 | **愿景分 ≠ 可运维分**；生产分看 tier0 + 真网冒烟 |

**趋势（仅 d4–d7 有 /10）**：d4(6) → d5(4.5) → d6(5.5) → d7(4)。  
**评注**：分数方向合理（CLI/进化最差），但 **d5 的 2/10 生产分仍偏情绪化**——更准确说法是「功能未接通」，不是「设计差」。

---

## d1 — 飞书适配器

**Wiki 快照**（`d1-audit-report.html`）  
- 形式：CEO→ENG→Review→QA 流水线，**无总分 /10**  
- 宣称：**4×P0**（token 竞态、WS 无熔断、disconnect 假停、同步下载阻塞 loop）+ 若干 P1  
- 估时：~13h  

### 现状核对（2026-05-20）

| Wiki 项 | 真源 | 评注 |
|---------|------|------|
| P0-1 token 无锁 | `feishu_adapter.py` 有 `_token_lock` + 多处 `with` | **已 addressed**（`341c1fd` / P2 线） |
| P0-4 同步下载阻塞 | 主路径有 **aiohttp 异步** `_feishu_download_image`；仍有 `requests.get` 分支 | **大部分已修**；Mimir 应用例压「纯图消息」盯 loop |
| P0-2 WS 熔断 | 需读 reconnect 循环 | **未逐项验收**；长跑/断网仍值得 Mimir 记 ISSUES |
| P0-3 disconnect 假停 | 需对照 `disconnect()` + thread join | **待专项冒烟**；与 gateway 常驻（E-001）不同问题 |
| 收图/识图 | P2-1/1b 已合；识图依赖 **OPENROUTER** | **产品阻塞在配置**，非 adapter 单模块 |

### 成熟度评价

- **有价值**：把飞书标成「独立高险模块」、token/WS/下载三类故障模式 — **仍成立**。  
- **不成熟**：83% Review 误报说明 **未用真网日志闭环**；部分 P0 在合码后 HTML 未降级。  
- **Wiki 分**：若 today 重评 ≈ **6.5/10 实现**（通道可用）/ **5/10 韧性**（熔断、shutdown 未证）。

### 宝贵建议

1. **验收标准固定化**：每条 d1 finding → `grep` 或飞书一步操作（写入 `mimir_prod_smoke.md` B 段）。  
2. **识图与收图分离**：M-002 只证明下载；vision 单独绑 M-005，避免 adapter 背锅。  
3. **勿再扩 feishu_adapter 行数**：卡片/HTML 逻辑继续放 `html_to_feishu_card`，adapter 只做 IO。  
4. **Mimir 训练**：T-02/T-03 + 盯 `230099` / `Image downloaded`（见 `MIMIR_D17` §3）。

### 结论一句

**d1 审计「方向对、时效旧」** — 当故障分类手册用，不当待办清单原样执行。

---

## d2 — 上下文 / 压缩 / C1

**Wiki 快照**  
- **7×P0 + 5×P1**，~12h  
- 核心：**三处孤儿 tool 修复**、Recovery 死代码、C1 丢 tool、压缩与 C1 打架、会话 100 条膨胀  

### 现状核对

| Wiki 项 | 真源 | 评注 |
|---------|------|------|
| 三处 orphan 修复 | `recovery_mixin` 委托 `compressor._sanitize_tool_pairs`；注释写 P0-1 三合一 | **架构上已统一入口**；tier0/冒烟无 `tool must` |
| MultiLevelRecovery 未接线 | `recovery_mixin` 以 **DecisionRing** 驱动 L2–L4 | **Wiki 过时**；d4 修复后路径已变 |
| C1 丢 tool | 需个案长对话复现 | **仍可能**；应用真实多轮 tool 会话测 |
| 压缩 vs C1 预算 | `MimirContextCompressor` + cd6b71d 链在 | **部分缓解**；无统一 token 仪表盘 |
| 会话 100 条 | gateway 历史 cap 需 grep | **配置债**，Mimir 只记录不修改 |

### 成熟度评价

- **有价值**：指出「上下文是隐形 P0」— **比飞书更深**，长期仍是最难债。  
- **不成熟**：把已合并的 orphan 三函数仍标三个 P0；Recovery「死代码」在 d4 后已改写。  
- **重评**：**6/10**（链路易断）/ **7/10**（已有压缩与 sanitize）。

### 宝贵建议

1. **单测不如「一条长会话录屏+日志」**：压缩触发前后 token 估算写进 ISSUES 即可。  
2. **禁止伪修复**：删光 `role=tool` — wiki 未强调，但实践已证明有害。  
3. **与 d4 合并读**：orphan/recovery 只维护 **compressor 一处 canonical**。  
4. **工程优先级**：d2 剩余 > d5 填 stub；先 **可观测 token 用量**（d6 Day-1）再改 C1 算法。

### 结论一句

**d2 是最该保留的审计**，但条目需按 **2026-05-20 代码** 重新打勾，否则工程师会重复劳动。

---

## d3 — Gateway 框架（God class）

**Wiki 快照**  
- `run.py` **9243 行**、5×P0（Task 泄漏、threading.Lock、SessionDB 静默、Cron 僵尸、clean_shutdown）  
- **Sprint S3 拆分** ~30h  

### 现状核对

| Wiki 项 | 真源 | 评注 |
|---------|------|------|
| God class | `run.py` **~1396 行** + **6 mixin**（E-002 `bccad39`） | **拆分已启动且有效**；未到 wiki 理想的 6 文件各 700 行 |
| Task 泄漏 | `393214e` TrackedTask；feishu 有 TrackedTask 包装 | **部分已修** |
| E-001 启动即退 | `should_exit_cleanly` **@property** | **已修**（拆分时回归，非 aiohttp） |
| threading in async | gateway 仍有多处 `threading.Lock` | **仍真实**；要逐点改 asyncio.Lock 或 executor |
| SessionDB 静默降级 | 未在本评注逐行验证 | 保留为 **P1 工程** |
| Cron 僵尸 | cron_mixin 已拆出 | **需硬重启 + SIGTERM 测试**（Mimir T-01 延伸） |

### 成熟度评价

- **有价值**：把 gateway 标为 **运维命门** — **完全正确**。  
- **不成熟**：行数写 9k 时吓人，但 **未跟踪 E-002 后体量**；估时 100h 吓退排期。  
- **重评**：**5.5/10 → 6/10**（能常驻）/ 架构 **6.5/10**（mixin 方向对）。

### 宝贵建议

1. **拆分规则**：`run.py` 只留装配与 `start_gateway`；新逻辑 **禁止** 再塞进 run。  
2. **Mimir 只验行为**：pgrep、Lark wss、无 `Gateway stopped`（T-01）— 不读 9k 行。  
3. **十条 backlog**（`GATEWAY_STABILITY_BACKLOG.md`）比 d3 HTML **更适合 Mimir 迭代**。  
4. **下一工程**：E-004 与 gateway 无关；gateway 下一刀应是 **SessionDB 告警** 或 **Cron shutdown**，单独立项。

### 结论一句

**d3 wiki 的最大价值是「必须拆」**；拆的第一刀已完成，HTML 应视为 **Phase 1 历史**。

---

## d4 — Agent 核心循环

**Wiki 快照**  
| 维度 | 分 |
|------|-----|
| 综合 | **6/10** |
| 架构愿景 | 8/10 |
| 实现纪律 | 5.5/10 |
| 生产 | 5/10 |

- P0：参数修复地狱、三路 recovery、**degrade_success 反了**、orphan 重复、**core_loop 3106 行拆分**  

### 现状核对

| Wiki 项 | 真源 | 评注 |
|---------|------|------|
| P0-0 degrade_success | `recovery.py` 仍有字段；需看 1bb652b 是否修逻辑 | **假定已修**（backlog 写 P0-0~3 ✅）；Mimir 可查 git show |
| P0-2 DecisionRing | `recovery_mixin` 明确 DecisionRing 驱动 | **已接线** |
| P0-3 orphan 重复 | 委托 compressor | **与 d2 重复计数** |
| P0-4 拆分 | 四 mixin + `core_loop` **~1295 行** | **E-003 完成度 ~70%**；核心仍偏大 |
| 参数修复 120 行 | `exec_mixin` 等 | **仍可能存在**；wiki 未给行号刷新 |
| M5 Ports | 仍在 | **仍是资产** — wiki 这点非常准 |

### 成熟度评价

- **最有洞察的一句**：「架构领先实现」— **2026-05-20 仍真**。  
- **不成熟**：把 d2 已有条目再在 d4 标 P0；分数细项缺 **tier0 162 tests** 证据。  
- **重评**：综合 **6.5/10**（P0 收口后）/ 生产 **5.5/10**（缺 OPENROUTER 与长跑）。

### 宝贵建议

1. **生产就绪定义**：`run_ralph_tier0.sh` 绿 + gateway 24h 常驻 + 飞书 M2/M3 — 比 /10 分有用。  
2. **下一拆分**：`exec_mixin` 若 >800 行，再拆 `tool_repair/`（wiki 建议保留）。  
3. **Mimir**：T-04 tool 链 + T-08 agent.log（#10）。  
4. **勿追求 wiki 的 30h 一口吃完**：按 **E-*** 小 PR。

### 结论一句

**d4 审计质量在 d1–d7 里最高** — 适合当 Agent 模块的「北极星文档」，但 P0 清单需与 E-003 对齐勾选。

---

## d5 — 自修 / 进化

**Wiki 快照**  
| 维度 | 分 |
|------|-----|
| 综合 | **4.5/10** |
| 生产可用 | **2/10** |

- P0：recorder 全局竞态、路径注入、**18/18 executor 存根**、模拟数据未标记  
- 双架构：`agent/` vs `mimicore/evolve/`  

### 现状核对

| Wiki 项 | 真源 | 评注 |
|---------|------|------|
| 存根 | `skills/.../self_evolution`、`mimicore/evolve` 仍在 | **仍真** — **不要 Mimir 填 19 个存根** |
| 路径注入 | skill_evolution | **仍高危**；E-007 未做 |
| recorder 全局 | execution_pipeline | **未验证** |
| simulated 标记 | 未验证 | E-007 范围 |
| persistent 竞争 | ADR `001-persistent-single-writer` 已有 | **设计有进展，实现未做**（P3-0） |

### 成熟度评价

- **有价值**：明确「进化不能上生产」— **必须听**。  
- **不成熟**：2/10 打击面过大；未区分「安全未做」vs「功能未做」。  
- **重评**：愿景 **7/10** / 生产 **2/10**（同意）/ **优先级应低于 d7、d6 Day-1**。

### 宝贵建议

1. **先写 ADR 再写 executor**（D5-ADR）— 双架构不收敛勿扩码。  
2. **单通路试点**：E-009 一条 FIX→SKILL e2e，胜过 19 存根。  
3. **Mimir 只做 T-09**：读 evolution_log + 一条观察，**禁止改 evolve 代码**。  
4. **与 persistent 截断史联动**：进化写盘必须服从单写者 ADR。

### 结论一句

**d5 wiki 是「刹车片」** — 防止未验收的自修上生产；不是 Mimir 实训场。

---

## d6 — 可观测性

**Wiki 快照**  
| 维度 | 分 |
|------|-----|
| 综合 | **5.5/10** |
| QA 测覆盖 | **2.75/10** |

- P0：insights `TOOL_CALL` 空分支、monitor 阈值空、health 未注册、RateLimitTracker 无锁  
- P1：五岛无总线、trajectory vs recorder 双 SoT  

### 现状核对

| Wiki 项 | 真源 | 评注 |
|---------|------|------|
| TOOL_CALL SQL | `insights.py` 有 `MetricType.TOOL_CALL` 与分支 | **需读 1007+ 行是否仍 `pass`** — wiki 可能仍对 |
| monitor 阈值 | 未逐行 | E-006 范围 |
| health 接线 | gateway status / core_loop finally | **部分有 get_monitor()** |
| 测试 | agent 有 insights 单测片段 | mimir_cli **仍零测**（d7 问题） |

### 成熟度评价

- **有价值**：「零件有了线没接」— **极准**，且与 tier0 绿不矛盾。  
- **不成熟**：未给出 **最小 Day-1 切片**（后来 backlog 才有 E-006）。  
- **重评**：**5.5/10 维持**；做完 E-006 可到 **7/10**。

### 宝贵建议

1. **Day-1 仅四刀**：E-006 的 0a–0d，**禁止** ObsBus 大重构。  
2. **Mimir T-10**：24h ERROR 基线 — 给工程提供「接线的目标数字」。  
3. **暴露给刘哥**：一条 `/health` 或 `gateway health` 输出里带 **last_error 计数** 即可。  
4. **QA 2.75/10 提醒**：可观测模块改完必须 **补 3 个 pytest**，不是 300 个。

### 结论一句

**d6 是工程下一阶段的「接线图」** — 优先于 d5 填 stub、d7 删 cli 之后的 P2。

---

## d7 — CLI 双轨

**Wiki 快照**  
| 维度 | 分 |
|------|-----|
| 综合 | **4/10** |

- P0：`CLI_CONFIG` 未定义、`cmd_chat` 反向依赖 `cli.py`  
- 46k 行双轨、16 命令重叠、mimir_cli **零 pytest**  
- Ship 顺序：P0#1→P0#2→删 cli.py  

### 现状核对

| Wiki 项 | 真源 | 评注 |
|---------|------|------|
| CLI_CONFIG | `mimir_cli/callbacks.py` 仍 `from cli import CLI_CONFIG` | **仍真 · E-004 未做** |
| chat 解耦 | 未验证 | E-005 |
| 删 cli.py | 仍存在根目录 `cli.py` | E-008 |
| delegate_tool 引 CLI_CONFIG | `tools/delegate_tool.py` | **隐性耦合** — wiki 未列 |

### 成熟度评价

- **有价值**：**双轨是真实风险**；Ship 顺序正确。  
- **不成熟**：46k 行吓人但未标 **哪 4h 阻塞发布**（其实 P0 很短）。  
- **重评**：**4/10 维持**；E-004 合并后 **5/10**。

### 宝贵建议

1. **E-004 极小 PR**：`mimir_cli/config.py` 定义 `CLI_CONFIG` 默认值 — **1h 级**。  
2. **删 cli 之前**：grep 全仓 `from cli import` / `import cli`（含 tools）。  
3. **Mimir T-11**：只负责 **复现 + ISSUES**，不修。  
4. **文档**：`MIMIR_ACTIVATE.md` 写清唯一推荐入口 `python3 -m mimir_cli` 或 `cli.py` 过渡期的矩阵。

### 结论一句

**d7 wiki 短、狠、准** — 与当前 backlog **E-004～E-008 完全一致**，可直接当工程合同。

---

## 阶段对照总表（评注分 vs Wiki）

| 阶段 | Wiki 分/形式 | 评注综合（2026-05-20） | 信任度 | 工程队列 |
|------|----------------|------------------------|--------|----------|
| d1 | 4×P0 清单 | 6.5 实现 / 5 韧性 | 中（时效旧） | 维护 P2 线 |
| d2 | 7×P0 | 6.5 易断 / 7 已修链 | 高（需刷新勾选） | 观察 + token 可视 |
| d3 | 5×P0 + 拆分 | 6 常驻 / 6.5 架构 | 中（行数过时） | E-002 ✅，后续 SessionDB/Cron |
| d4 | **6/10** | **6.5** | **高** | E-003 ✅，exec 再拆 optional |
| d5 | **4.5/10** | 愿景7 / 生产2 | 高（刹车） | E-007、E-009 |
| d6 | **5.5/10** | 5.5 | 高 | **E-006 优先** |
| d7 | **4/10** | 4 | **极高** | **E-004 下一刀** |

---

## 给 Mimir 的「审计思维」训练（迭代 / 进化）

不用改 wiki，用本文练习 **三代循环**：

```text
1. 读 wiki 一条 P0（例如 d1 token 无锁）
2. 真源验证：rg '_token_lock' gateway/platforms/feishu_adapter.py
3. 结论写入 MIMIR_ISSUES：已修 / 仍存 / 无法复现 + 证据一行
4. 若仍存 → 标「移交工程」并引用 E-* 或新立项
```

**进化（轻量）**：每完成一轮 T-01～T-11，在回报里加：

- 「哪条 wiki 说法已被证伪」  
- 「哪条 wiki 说法仍真且未排期」  

刘哥回来后用此表调优先级，比改 HTML 更值钱。

---

## 工程优先级（评注后的统一建议）

在 **不推翻** `MIMIR_EXEC_BACKLOG` 前提下，评注层推荐顺序：

1. **E-004**（d7 P0，短、解锁 callbacks）  
2. **Mimir T-01～T-11**（post-commit 回归 + ISSUES 输入）  
3. **E-006 Day-1**（d6 接线，可观测）  
4. **E-005 / E-008**（d7 解耦与删 cli）  
5. **E-007 / E-009**（d5 安全 + 单通路进化）  
6. d1/d3 **韧性** 专项（熔断、disconnect）— 有冒烟证据再立项  

**明确后置**：d5 大规模填 stub、ObservabilityBus 大重构、wiki 中的 ~100h 总账。

---

## 相关文档

| 文档 | 关系 |
|------|------|
| `docs/MIMIR_D17_AUDIT_AND_TASKS.md` | Mimir 可执行任务 + 提示词 |
| `docs/MIMIR_EXEC_BACKLOG.md` | 统一队列 E-* / M-* |
| `docs/GATEWAY_STABILITY_BACKLOG.md` | 十条运维向 |
| `docs/mimir_prod_smoke.md` | 真环境里程碑 A |
| `docs/MIMIR_CLARIFY_BASELINE.md` | 路径与 mimicore 只读基线 |

---

*本文随代码演进由 Cursor 增补；修改 wiki HTML 非必须。下次刘哥离线前可说「刷新评注」以更新「现状核对」表。*
