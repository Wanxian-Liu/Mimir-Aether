---
name: mimiraether-verification
description: >
  收尾硬门控：提交/汇报前必须验证。与 brainstorming（入口门控）配对的出口门控。
  灵感源自 obra/superpowers verification-before-completion 技能。
  强制在 commit/push/"做完了"/"成功了"之前执行验证序列，防止"以为做完了但实际没验证"。
version: 1.1.0
auto_load: true
triggers:
  - 完成
  - 成功
  - 报告
  - 提交
  - commit
  - push
---

# MimirAether Verification — 收尾门控

**核心铁律：没验证 = 没做完。**

与 brainstorming（入口门控）配对：**设计批准才能开始，验证通过才算结束。**

---

## ## 触发条件

**必须触发（硬门控）**：

| 场景 | 判定 |
|------|------|
| 用户说"提交"/"push"/"做完了"/"搞定" | 🔴 触发 |
| Agent 认为任务完成，准备 commit | 🔴 触发 |
| 任何代码改动后准备声明"完成" | 🔴 触发 |
| 多文件改动（3+ 文件）完成后 | 🔴 触发 |

**不触发**：

| 场景 | 判定 |
|------|------|
| 纯查询/信息回复 | ⚪ 放行 |
| 中间步骤（明确还有后续） | ⚪ 放行 |
| plan-mode 中的子任务（由 plan 的 verification 覆盖） | ⚪ 放行 |

---

## 验证四层

### 第 0 层：验证基线 (Baseline) — SkillOpt 拒绝编辑缓冲区

**改代码前必须先建立验证基线。** 没有基线=不知道改的有没有用。

```python
# 修改前：读盘快照
import json
path = "/home/rayliu/.mimiraether/data/persistent.json"
with open(path) as f:
    baseline = json.load(f)
# 记录关键计数指标
kd_before = len(baseline['memory']['key_decisions'])
lp_before = len(baseline['memory']['learned_patterns'])
bc_before = len(baseline['memory']['behavioral_constraints'])
size_before = path.stat().st_size

# 修改后：对比验证
# 只有变化是预期的且数据未退化才接受
```

**SkillOpt 规则 (arXiv:2605.23904)：**
- **拒绝编辑缓冲区**：验证分数没严格提高就不接受修改
- **文本学习率预算**：单次改动限制在 3 个函数 / 30 行以内
- **epoch-wise 慢更新**：从 1-3 轮编辑开始，逐步增加
- **>3 次不通过 → 回退**：behavioral_constraints #7

当验证 FAIL 时，不走"再微调一下"路线——看 baseline 对比报告，确认是哪个指标退化了。

---

### 第 1 层：自动化门禁 (Gate)

```
./run_ralph_tier0.sh    ← 必须全绿 (Gate1+Gate2+Gate3)
```

- Gate1: 导入检查（无 broken imports）
- Gate2: 单元测试
- Gate3: 契约测试

**不通过 = 不能提交。没有例外。**

---

### 第 2 层：一致性检查 (Consistency)

```
1. 零残留引用检查：
   - 改了 agent/ → 确认 import 链不断
   - 删了模块 → grep 确认零残留引用
   - 新增模块 → 确认 __init__.py 导出

2. 「声称 vs 盘上」检查：
   - 声称"写入了" → read_file 确认盘上有
   - 声称"压缩了" → read_file persistent.json 确认条数减少
   - 声称"已提交" → git status 确认干净（除运行时文件）

3. 文件完整：
   - 新增文件 → git status 确认已 tracked
   - 不应该出现的文件 → 确认在 .gitignore
```

### 第 3 层：飞书实战验证 (Live)

仅当改动涉及 `gateway/platforms/feishu_adapter.py` 或 `model_tools.py` 或工具注册时：

```
1. 确认 Gateway 进程运行: ps aux | grep gateway
2. 确认飞书连接: 日志中 "feishu" + "connected"
3. 确认消息可收发: 发一条简单的飞书消息测试
4. 确认错误日志无新增异常
```

**反模式**：做了 gateway 改动但跳过飞书实战验证 → 上次循环的根因。

---

### 第 4 层：自问清单 (Honest Check)

完成前必须诚实回答：

```
□ 我声称做完了 X。我真的验证了 X 能用吗？——读盘确认数据变了再开口
□ 有没有"我假设它能用所以就算了"的东西？
□ 用户原始请求是什么？我做的和请求一致吗？
□ 有没有 dangling 改动（改了 A 但忘了改依赖 A 的 B）？
□ 如果我是用户，我会对这个结果满意吗？
```

**如果任何一个答案是"不确定"或"否" → 没做完。**

---

## 验证输出格式

验证完成后，输出简洁报告：

```
━━━ 验证报告 ━━━━━━━━━━━━━━━
- "声称 vs 盘上"检查:      ✅ (列证据)
- 残留引用:               ✅ (0 残留)
- 飞书实战:               ✅ / N/A
- 自问清单:                5/5 ✅
━━━━━━━━━━━━━━━━━━━━━━━━━━
判定: PASS / FAIL
```

---

## 验证度量指标（参考 GDM AI Control Roadmap #12）

每次验证完成后，计算以下指标：

| 指标 | 含义 | 阈值 |
|:----|:-----|:----:|
| **Coverage** | 验证覆盖了哪些层（1-4）| ≥3 层 |
| **Recall** | 验证发现了多少问题 / 实际有多少问题 | ≥80% |
| **Time-to-response** | 从检测到问题到生成验证报告的时间 | ≤30s |

**不达标 → 标记为 FAIL，追加步骤后重新验证。**

## R1-R3 升级路径（验证失败时）

当验证 FAIL 时，按以下层级 escalate：

| 级别 | 动作 | 说明 |
|:----:|:-----|:-----|
| **R1 — 隔离** | 阻止 commit/push。生成失败报告，标记 blocking issue | 默认动作 |
| **R2 — 回滚** | 如果代码已部署但验证发现严重问题，回滚到上一个已知良好版本 | 仅用于生产环境问题 |
| **R3 — 关闭** | 如果检测到系统性不可信（同一模式连续 3 次验证 FAIL），停止当前任务批次，等待人工介入 | 最终防线 |

**R1 是默认动作。R2 / R3 由你触发，我不自动执行。**

## 六种检测类型（参考 GDM AI Control Roadmap）

| 检测类型 | 在我们的验证层中的对应 | 状态 |
|:--------|:--------------------|:----:|
| **Alignment testing** — Ralph tier0 | L1 自动化门禁 | ✅ |
| **CoT monitoring** — 检查 LLM 输出推理链 | 蒸馏时检查 `run_dream_cycle` 的输出，确认 LLM 成功返回压缩结果 | 🟡 需强化 |
| **Action monitoring** — 检查行为一致性 | L2 一致性检查（声称 vs 盘上） | ✅ |
| **PR monitoring** — 代码变更审查 | requesting-code-review skill | ✅ |
| **Honeypots** — 预设陷阱检测 | L4 自问清单 + Anti-Rationalization Table | ✅ |
| **Activations monitoring** — 内部状态（技术上无法实现） | — | ❌ 跳过 |

## 与 MimirAether 技能生态的协作

```
brainstorming (设计门控)
  → plan-mode (分解)
    → subagent-driven-dev (执行)
      → verification (本技能 — 收尾门控)
        → commit/push (完成)

蒸馏执行专用验证（与 mimiraether-distillation-execution 联动）：
  1. terminal 写盘后 → 必须 read_file 读回 persistent.json
  2. 不凭终端"写入成功"文本汇报
  3. 验证 kd ≤ 20 / lp ≤ 30 / bc ≤ 8 / 100% tip_type+cause_chain
```

| 技能 | 协作方式 |
|------|---------|
| `mimiraether-brainstorming` | 入口门控配对 — 设计批准开始，验证通过结束 |
| `mimiraether-ralph-core` | Ralph tier0 是验证第 1 层的执行引擎 |
| `mimiraether-distillation-execution` | 蒸馏操作的执行路径铁律 + 验证铁律（加载此技能获取完整规则） |
| `gateway-feishu-crash-recovery` | 如果飞书验证失败 → 加载此技能诊断 |

---

## 关键原则

| 原则 | 说明 |
|------|------|
| 自动化优先 | 能脚本验证的不靠人眼 |
| 声称必须证明 | 说"已完成"必须能证明——先读盘再开口 |
| 飞书改动必实战 | gateway 改动不跳过 Live 验证 |
| 诚实自问 | 最后的防线是诚实 |
| 非代码迭代 | 写作/分析任务在 verify 前先走 `mimiraether-evaluator-optimizer` 循环 |

---

## 自我验证循环 (Self-Validation Cycle)

当 LLM 输出包含"已完成"、"已验证"、"已修"、"成功了"、"已修复"、"没问题了"等声明性结论时：

1. **自动触发** — 对声明涉及的文件调用 `read_file` / `json.load` 确认盘上真实状态
2. **如果不匹配** — 阻止该声明输出，追加 `[BLOCKED:verify-before-report]` 消息
3. **只有通过** — 盘上数据与声明严格一致才允许输出
4. **记录日志** — 每次验证结果追加到 `verification_results.jsonl`，供 `self_evolution.collect_metrics()` 读取

**这个循环在下一次"完成"声明时自动生效。** 不需要手动触发。

---

## 反模式与陷阱

1. **跳过验证**：「这个改动太小，不用验证」 — 上次 MAX_MESSAGE_LENGTH 也是"小改动"
2. **只跑 Ralph，不做一致性**：「测试过了就行」 — 残留引用不导致测试失败
3. **飞书实战被遗忘**：每次循环都在这里断开，不是验证有问题，是上下文污染
4. **自问清单敷衍**：全部打勾但实际没想 — 这骗的是自己
5. **声称"写入了"但不读盘确认** — 这是本轮对话 15 轮循环的根因。behavioral_constraints 第 6-7 条已禁止此行为

---

## Anti-Rationalization Table

LLM 擅长自圆其说。以下是在验证环节最常用的借口——以及为什么它们不成立。

| LLM 可能会说 | 为什么不成立 |
|-------------|-----------|
| **"这个改动太小了，不用验证"** | MAX_MESSAGE_LENGTH 也是"小改动"——改一行就崩了飞书收发。改动大小与风险无关。 |
| **"Ralph 过了就行了"** | Ralph 不检查残留引用、不检查文件完整、不检查盘上数据是否真实写入。Ralph 通过 ≠ 任务完成。 |
| **"飞书我上次测过了"** | 每轮 gateway 改动都可能引入新问题。"上次测过"不是豁免凭证——尤其是上下文被压缩后。 |
| **"我知道盘上有"** | 你知道的不是证据。每次说"xx在盘上"时——查真实路径；x到正确嵌套层；用 json.load 而非凭记忆确认。 |
| **"路径我知道"** | 蒸馏 16 轮每次都说"路径正确"——但读了 16 次 `d['key_decisions']`（空）而非 `d['memory']['key_decisions']`（20条）。先 `type()` + `keys()` 打印实际结构再报。 |
| **"我之前读过了"** | 每个会话、每个任务、每个文件——从头验证。之前读过的结果可能被后续操作覆盖。fresh eyes，fresh reads。 |
| **"这跟验证无关"** | 每句话都可以用"验证了吗？"反问自己。如果答案是"没有"——那就是跟验证有关。 |
| **"我先汇报，等一下再读盘验证"** | 等一下就永远不会验证——这是 16 轮蒸馏教训的精确根因。**必须先验证再开口。没有"等一下"。** |