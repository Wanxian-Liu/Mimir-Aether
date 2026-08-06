# [DORMANT] mimiraether-ralph-core

**沉寂时间**: 2026-08-01T13:06:03.714759+00:00
**原始分类**: mimiraether
**描述**: Ralph模式核心约束 — 最小注入：工具触发规则 + 反瘫痪 + 进度信号。
**触发阈值**: 60天未触碰

---

## 技能要点

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

---

> 此胶囊由 Skill Curator 自动生成。原始技能已移入 .dormant/。
> 调用 `skill_view("mimiraether-ralph-core")` 即可自动唤醒。
