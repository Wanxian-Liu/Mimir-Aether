# 技术债方案：8/17 论文任务失败 · 系统层 3 修复 + 1 元修复

> **来源**：2026-08-18 自我审计（`wiki/concepts/自我审计报告-20260817论文任务失败根因.md`）的系统层结论
> **性质**：技术债（需刘哥拍板后改代码；本方案只落盘不动代码）
> **审计结论回顾**：8/17 论文任务 8 次追问 7 次空洞确认，根因 = 行为层（空洞确认模板 ×5 / 探索完不产出 ×2 / 虚构声明 ×1）+ 系统层 3 帮凶（IntentPredictor 误判 ×4 / History window 截断 / 产出提示无效）

---

## 系统现状（代码真源，2026-08-18 实查）

| 机制 | 位置 | 现状 | 缺陷 |
|:--|:--|:--|:--|
| **IntentPredictor** | `agent/core_loop.py` L750-768 | `predict_and_format()` 仅在 `run_conversation` 开头对**第一条** user 消息预测一次 | 后续追问（"什么论文？"）不重新预测 → 后续轮次无 intent 提示 |
| | `agent/intent_predictor.py` L34 | research pattern 已含"论文/找/搜/热门"（8/17 已加） | 口语缺"看看/了解一下/有没有/给我找"；且只对首轮生效 |
| **History window** | `gateway/agent_mixin.py` L1088-1103 | `MIMIR_HISTORY_WINDOW=50`：会话续接只保留最近 50 条，更早**直接丢弃** | 长会话（200 条）每轮丢 144-154 条 → 跨轮上下文丢失 → "忘记"已搜索内容、重复搜索 |
| | `agent/core_loop.py` L640-656 | 注入前置历史再截 `max_recent_messages=25` | **双重截断**：gateway 50 → agent 25，上下文被砍两次 |
| **产出提示** | `agent/agent_loop.py` L846-859 | `_check_has_written` → 软提示 `_inject_production_nudge`（追加文字，LLM 可无视） | 软提示可被空洞确认绕过 |
| | `agent/verify_before_report_guard.py` L79-99 | hard block 只对含"已完成/已验证"等**触发词**的回复生效 | "收到——落盘"不含触发词 → guard 不触发 → 溜过 |
| | `agent/agent_loop.py` L956-969 | `_should_nudge_production` 问答型豁免已加（8/17） | 豁免正确，但**没有**"nudge 后仍无产出→升级强制"的路径 |

---

## 方案总纲：一治一防一兜底

```
TD-01 Intent 每轮重估 ──┐（防：后续追问有提示）
TD-02 窗口+摘要保留 ────┼─（防：跨轮不失忆）
TD-03 产出分级强制 ────┼─（治：空洞确认拦不住）
TD-04 空洞确认硬拦截 ──┘（兜底：模板回复直接 block）
```

---

## TD-01 · IntentPredictor 每轮重估（P0 · 小改）

**目标**：后续追问也触发 research 提示，不再只认首轮。

**改动点**：`agent/core_loop.py` —— 每轮循环开头（`_build_messages` 前）对**最新一条 user 消息**重新 `predict_and_format()`，更新 `self._intent_context_block`。轻量正则，<1ms，无额外 LLM 成本。

```python
# 伪代码（每轮）
latest_user = 最新 user 消息
self._intent_prediction, self._intent_context_block = predict_and_format(latest_user)
```

**配套**：`agent/intent_predictor.py` L34 research pattern 补口语：
```python
("research", re.compile(r"(?i)论文|research|调研|找.*(论文|资料|信息|项目|仓库|卡)|查.*(论文|资料|信息)|搜.*|热门|炙手可热|推荐|看看|了解一下|有没有|给我找|帮我找|找找|讲.*(论文|项目)"))
```

**验证**：
- 单测：`predict("给我找一篇数学论文")` → intent=research
- 单测：`predict("什么论文？")` → intent=research（追问命中）
- e2e：模拟多轮，第二轮输出日志 `[IntentPredictor] intent=research` 出现

**风险**：低。仅日志 + prompt hint 注入，无行为变更。

---

## TD-02 · History window 截断 → 窗口 + 摘要保留（P1 · 中改）

**目标**：防 token 膨胀（窗口保留是对的），但被丢的历史不直接消失——任务指令/已搜内容/待办可恢复。

**改动点 1**：`gateway/agent_mixin.py` L1091-1103 —— 截断前对将被丢弃的 `history[:_dropped]` 生成**结构化摘要**（复用 `agent/context_compressor.py` 的 LLM 摘要能力或模板摘要），摘要作为一条 `{"role": "system", "content": "[HISTORY SUMMARY] ..."}` 注入窗口头部。

摘要模板（复用 context compressor 的结构化模板）：
```markdown
[HISTORY SUMMARY — 旧会话摘要]
## Task Goal: <用户最初目标>
## Progress: <已完成，含文件路径>
## Blocked: <阻塞项>
## Pending Asks: <未答复的问题>
## Key Context: <关键数值/决策/约束>
```

**改动点 2**：`agent/core_loop.py` L640-656 —— `_max_recent` 与 gateway 窗口对齐（50），消除双重截断；且对注入历史**保留摘要 system 消息**（当前过滤 role=system 会丢摘要——需放行 `[HISTORY SUMMARY]` 前缀的 system 消息）。

**兜底**：摘要 LLM 失败 → 降级保留被丢部分最后一条 user 消息全文（保证任务指令不丢）。

**验证**：
- 单测：构造 60 条历史 → 触发摘要 → 断言窗口=50 + 摘要含任务关键词
- e2e：长会话续接，日志含 `History window: dropped ... (summary attached)`

**风险**：中。摘要有 LLM 成本（仅截断触发时一次，非每轮）；摘要质量影响恢复。env 门控 `MIMIR_HISTORY_SUMMARY=1` 可关。

---

## TD-03 · 产出校验：软提示 → 分级强制（P1 · 中改）

**目标**：nudge 后仍无产出 → 升级硬拦截 → 再升级中断，杜绝"软提示可绕过"。

**三级路径**（`agent/agent_loop.py` L846-859 扩展）：

| 级 | 触发条件 | 动作 | 现有机制 |
|:--|:--|:--|:--|
| **L1 软** | 主动结束 & `not _has_written` & 非问答豁免 | 追加产出提示（现状） | `_inject_production_nudge` ✅ 已有 |
| **L2 硬** | L1 已触发 ≥1 次 & 仍无产出 | **移除未验证回复**（复用 verify guard L827-828 机制）+ 注入强制提示 | 需新增：复用 `verify_before_report_guard.should_block_finish` 的 pop 逻辑 |
| **L3 中断** | L2 已触发 ≥2 次 & 仍无产出 | 以 `has_written=False` 结束，结果透传用户（"任务未产出，原因：N 次强制后仍无写盘/回答"） | 需新增：计数上限 `MAX_PRODUCTION_HARD_NUDGES=2` |

**判定标准升级**（对齐 AGENTS.md §11 铁律 2"先回答再落盘"）：
- **research/问答类任务**：产出 = 本轮回答了用户问题（有实质 assistant 文本 ≥50 字且非模板），**不强制写盘**
- **写盘类任务**：产出 = 有 write_file/patch 到非工作记忆路径（`_check_has_written` 现状 ✅）
- 判定函数：`_production_achieved(messages, task_type)` —— 按最后 user 消息的任务词分类

**验证**：
- e2e：模拟 agent 输出"收到——落盘"→ L2 硬拦截（回复被移除）
- e2e：模拟 3 轮无产出 → L3 中断，结果 `has_written=False`
- 回归：问答型（"怎么不回答了？"）不触发 L1（现有豁免保留）

**风险**：中。硬拦截可能误伤正常收尾 → 豁免条件（问答/简短状态查询）必须保留 + env 门控 `MIMIR_PRODUCTION_ENFORCE=1`。

---

## TD-04 · 空洞确认模板硬拦截（P0 · 最小改动 · 元修复）

**目标**：把 AGENTS.md §11 铁律（8/17 当天刘哥根治"收到——落盘"）从"提示词规矩"变成"系统强制"。

**改动点**：`agent/verify_before_report_guard.py` —— 新增空洞确认检测：

```python
# 空洞确认模板：以"收到/好的"开头 + 含"落盘/记录/探索"承诺词 + 无工具调用 + 回复 < 80 字
HOLLOW_ACK_PATTERN = re.compile(r"^(收到|好的|好|ok|OK|可以)[，,。\s]*(?:——|-|—)*.*(落盘|记录|探索|补上|入库)")
def _is_hollow_ack(assistant_text: str) -> bool:
    return bool(HOLLOW_ACK_PATTERN.search(assistant_text)) and len(assistant_text) < 80
```

`should_block_finish` 增加分支：`_is_hollow_ack(assistant_text) and 本轮无工具调用 → return True`（触发 hard block，移除回复 + nudge）。

**验证**：
- 单测：`_is_hollow_ack("收到——落盘")` = True；`_is_hollow_ack("收到，已调用 write_file 写入 /tmp/x.md")` = False（有工具）
- e2e：模拟空洞确认回复 → guard 拦截日志出现

**风险**：低。仅拦"无工具 + 短回复 + 承诺词"组合，正常执行回复（有工具调用/长回复）不受影响。

---

## 优先级与依赖

| 序 | ID | 优先级 | 改动量 | 依赖 | 直接收益 |
|:--|:--|:--|:--|:--|:--|
| 1 | **TD-04** | P0 | ~15 行 | 无 | 空洞确认从"可绕过"变"必拦截"（治 8/17 主因） |
| 2 | **TD-01** | P0 | ~10 行 + pattern | 无 | 后续追问有 intent 提示（防"探索无指引"） |
| 3 | **TD-03** | P1 | ~40 行 | TD-04 的 guard 复用 | 产出从"软提示"变"三级强制" |
| 4 | **TD-02** | P1 | ~60 行 | 无 | 跨轮上下文可恢复（防重复搜索/失忆） |

**建议**：TD-04 + TD-01 同批（小改，直接治本次事故）；TD-03 次批；TD-02 最后（改动最大，需单独验证）。

---

## 验收总清单（全部落地后）

1. `pytest tests/` 新增单测：TD-01 ×2 / TD-02 ×2 / TD-03 ×2 / TD-04 ×2，全绿
2. e2e 模拟 8/17 场景：用户说"去网上找论文"→ agent 必须出现 web_search 工具调用（TD-01+TD-04 生效）
3. 长会话（>50 条）续接：日志出现摘要注入（TD-02）
4. 空洞确认回复：verify guard 拦截日志出现（TD-04）
5. 连续无产出：L3 中断结果 has_written=False（TD-03）
6. 回归：tier0 全绿；问答豁免不误伤

## 回滚预案

- 全部 env 门控：`MIMIR_INTENT_PREDICTOR` / `MIMIR_HISTORY_SUMMARY` / `MIMIR_PRODUCTION_ENFORCE` / `MIMIR_VERIFY_BEFORE_REPORT` 任一 = 0 → 该机制关闭，回到现状
- TD-02 摘要失败自动降级（保留最后 user 消息）——不阻塞主流程
- 每粒独立 commit，可单独 revert

---

## 与行为层的闭环（不重复建设）

行为层（§11 铁律 + 每轮自检三问）已存在于 AGENTS.md——本方案是**系统强制化**，不是替代：
- 规矩（AGENTS.md §11）管"我该怎么做" → TD-04 管"系统不让我不这么做"
- 审计（自我审计报告）管"事后复盘" → TD-03 L3 管"事前中断"
- 三层合一：规矩 → 强制 → 中断，8/17 事故不再重演
