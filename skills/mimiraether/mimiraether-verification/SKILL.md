---
name: mimiraether-verification
description: >
  收尾硬门控：提交前必须验证。与 brainstorming（入口门控）配对的出口门控。
  灵感源自 obra/superpowers verification-before-completion 技能。
  强制在 commit/push/"做完了"之前执行验证序列，防止"以为做完了但实际没验证"。
version: 1.0.0
auto_load: false
---

# MimirAether Verification — 收尾门控

**核心铁律：没验证 = 没做完。**

与 brainstorming（入口门控）配对：**设计批准才能开始，验证通过才算结束。**

---

## 触发条件

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

2. 「声称 vs 实际」检查：
   - 声称"hermes_cli 已删除" → ls hermes_cli/ 确认不存在
   - 声称"零残留" → grep -r "from hermes_cli" 确认 0 结果
   - 声称"已提交" → git status 确认干净（除运行时文件）

3. 文件完整：
   - 新增文件 → git status 确认已 tracked
   - 不应该出现的文件 → 确认在 .gitignore
```

---

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
□ 我声称做完了 X。我真的验证了 X 能用吗？
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
Gate1 导入     ✅/❌
Gate2 单元     ✅/❌ (N passed)
Gate3 契约     ✅/❌ (N passed)
残留引用       ✅/❌ (0/X 残留)
飞书实战       ✅/❌ / N/A
自问清单       5/5 ✅
━━━━━━━━━━━━━━━━━━━━━━━━━━
判定: PASS / FAIL
```

---

## 与 MimirAether 技能生态的协作

```
brainstorming (设计门控)
  → plan-mode (分解)
    → subagent-driven-dev (执行)
      → verification (本技能 — 收尾门控)
        → commit/push (完成)
```

| 技能 | 协作方式 |
|------|---------|
| `mimiraether-brainstorming` | 入口门控配对 — 设计批准开始，验证通过结束 |
| `mimiraether-ralph-core` | Ralph tier0 是验证第 1 层的执行引擎 |
| `gateway-feishu-crash-recovery` | 如果飞书验证失败 → 加载此技能诊断 |

---

## 关键原则

| 原则 | 说明 |
|------|------|
| 自动化优先 | 能脚本验证的不靠人眼 |
| 声称必须证明 | 说"已完成"必须能证明 |
| 飞书改动必实战 | gateway 改动不跳过 Live 验证 |
| 诚实自问 | 最后的防线是诚实 |
| 非代码迭代 | 写作/分析任务在 verify 前先走 `mimiraether-evaluator-optimizer` 循环 |

---

## 反模式与陷阱

1. **跳过验证**："这个改动太小，不用验证" — 上次 MAX_MESSAGE_LENGTH 也是"小改动"
2. **只跑 Ralph，不做一致性**："测试过了就行" — 残留引用不导致测试失败
3. **飞书实战被遗忘**：每次循环都在这里断开，不是验证有问题，是上下文污染
4. **自问清单敷衍**：全部打勾但实际没想 — 这骗的是自己
