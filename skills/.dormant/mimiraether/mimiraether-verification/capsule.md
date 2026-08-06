# [DORMANT] mimiraether-verification

**沉寂时间**: 2026-07-31T08:41:50.213221+00:00
**原始分类**: mimiraether
**描述**: 收尾硬门控：提交/汇报前必须验证。与 brainstorming（入口门控）配对的出口门控。 灵感源自 obra/superpowers verification-before-completion 技能。 强制在 commit/push/"做完了"/"成功了"之前执行验证序列，防止"以为做完了但实际没验证"。

**触发阈值**: 60天未触碰

---

## 技能要点

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



... (truncated)

---

> 此胶囊由 Skill Curator 自动生成。原始技能已移入 .dormant/。
> 调用 `skill_view("mimiraether-verification")` 即可自动唤醒。
