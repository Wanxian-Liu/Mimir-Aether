# [DORMANT] mimiraether-agent-iq-measurement

**沉寂时间**: 2026-11-18T12:02:31.844928+00:00
**原始分类**: mimiraether
**描述**: 测「Agent 综合智商」的外部标尺与方法学（ARC-AGI-3 RHAE / Gaia2 cost Pareto / METR 度量学 / τ²-bench pass^k / AMA-Bench）+ 自评机制的 7 条硬前置（量具存活 / 反背题 / 成本口径 / 异源裁判 / 失败注入 / 人类基线 / 时间维度）。触发词：你进化了么/评分/benchmark/IQ 复评/测智商/进化评估。
**触发阈值**: 60天未触碰

---

## 技能要点

# 测 Agent 综合智商：外部标尺 + 自评的硬前置

> 建立 2026-09-19（IQ 第三次复评 · 首次下跌 5.62→5.585 后固化）。
> 用途：**任何「打分 / 复评 / 你进化了么」类任务，先读本技能，再动手。**

## 0. 第一原则（本次实证换来的）

> **修好尺子 ≠ 变聪明；而尺子坏掉时会静默表现为「没有反馈」。**
> 实证：反馈环 `feedback_events.jsonl` 停摆 35 天无人发现 ⇒ 直接导致 #3 维度 5.5→4.5，总分首次下跌。
> 而同期「让尺子可信」的产出（门禁治本/记忆保真/卫生闸）在 10 维表里**一分不加**。

## 1. 打分前的 7 条硬前置（任一不过 ⇒ 只报「仪器状态」，不出总分）

| # | 前置 | 判据（可执行） |
|:-:|:--|:--|
| 1 | **量具存活** | 跑 `~/src/MimirAether/.venv/bin/python3 scripts/iq_reeval_ready_probe.py --skip-machine`：`READY … gauges=3/3` ⇒ 过；`NO-SCORE …` ⇒ 不过，**只报仪器状态不出分**。判**四件事**（存在 / 可解析 / schema / 新鲜度），不是只判 `test -e`——存在性检查是假绿口（文件在、内容停更，照样能算出一个不可信的分）。缺失 ⇒ 标 **N/A，不标 0**（「无数据」≠「无失败」） |
| 2 | **反背题** | 分数必须用 **held-out 题集**报；旧固定题集降级为「回归对照」，**不再作为能力证据** |
| 3 | **成本口径** | 每维分数附 token/秒/元；**无 cost 字段的分数不许进表**（否则重演「#7 触顶 8.0 vs 实测 p50 13.6s」） |
| 4 | **异源裁判** | 自评须由 **≥1 个异源 agent** 独立重打；**裁判不得同源同模型**（self-attribution bias 已实证：某厂商自评通胀 CI [35.9, 38.3]） |
| 5 | **失败注入** | 每个核心机制 ≥1 个「中途注入故障」臂 + 断言「失败可听」（Gaia2 的 noise/controlled failures 范式） |
| 6 | **人类基线** | 分数要么挂人类基线，要么明写「内部相对分，无外部意义」（ARC 的 RHAE = 对比人类第二好成绩） |
| 7 | **时间维度** | 显式记录「停滞天数」；Gaia2 里 `time` 分片是所有模型最难项 |

## 2. 外部标尺全景（2026-09 实检 · 只列出处可查的）

| 机制 | 出处 | 测什么 | 关键设计 / 数字 |
|:--|:--|:--|:--|
| **ARC-AGI-3** | arXiv:2603.24621 · arcprize.org/arc-agi/3 | 交互式：探索→建模→**自己推断目标**→规划。**无语言无指令** | 人类 **100%** 可解；frontier 模型 **<1%**（Gemini 3.1 Pro 0.37% / GPT-5.4 0.26% / Opus 4.6 0.25%）。指标 **RHAE**（相对人类动作效率，对比人类第二好，平方惩罚，逐关加权）。**官方榜禁 harness**：手搓 harness 在已见环境 97.1%、未见环境 **0.0%** ⇒ harness 分 ≠ 智商分 |
| **Gaia2 + ARE** | huggingface.co/blog/gaia2 · github meta-agents-research-environments | 真实助理：读+写、**歧义/噪声/受控失败**、时间敏感、动态事件 | 1000 场景；分片 `execution/search/time/ambiguity/adaptability`；**最难 = time**。**报 cost-performance Pareto（调用数 + 输出 token）** |
| **METR 度量学** | metr.org/notes/**2026-07-24-metrics-of-model-ability** · arXiv:2503.14499 | **方法学**：能力 = 分数-投入曲线 $s_A(x)$ vs 人类 $s_H(x)$ | 五种度量：固定投入取分 / 平台期 / **固定分数取最小投入** / **expenditure horizon** / **time horizon**。可

... (truncated)

---

> 此胶囊由 Skill Curator 自动生成。原始技能已移入 .dormant/。
> 调用 `skill_view("mimiraether-agent-iq-measurement")` 即可自动唤醒。
