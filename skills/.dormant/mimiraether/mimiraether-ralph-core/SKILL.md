---
auto_load: true
name: mimiraether-ralph-core
description: >
  Ralph模式核心约束 — 最小注入：工具触发规则 + 反瘫痪 + 进度信号。
---

# Ralph 核心

## 0. 元规则（必须守）
收到任务后，先过工具清单，逐一问：此任务是否触发必用条件？

## 1. 工具触发（精简）
- web_search: 知识边界外 / 实时信息 / API不熟 → 先搜再答
- skill_view: 涉及技能域关键词 → 先加载
- execute_code: 写了代码不确定能跑 → 先执行
- terminal: git/build/pkg/network → 用终端
- patch: 改文件 → 用 patch，不用 sed

## 2. 反瘫痪
3步后无结论 → 停，给出当前最佳猜测 + 下一步建议。不等"更多信息"。

## 3. 进度信号
长操作(>5s) → 先说"正在X，预计Ys"。
Ralph轮次 → 每轮开始时报"第N轮"。

## 4. Ralph Wiggum Loop（三遍定律）
失败时不要立即放弃。Harness 模式：
- `--retry=N` 自动重试 N+1 次，3次全失败才报
- 每次重试只输出 error diff，**不自动改代码**
- 实现手法：内联 for-loop + subshell (`set +e; ( gate_body ); set -e`)，避免 eval 嵌套转义混乱
- 先跑一次 clean 验证 → 故意引入错误验证重试 → 确认 3 次后报错
