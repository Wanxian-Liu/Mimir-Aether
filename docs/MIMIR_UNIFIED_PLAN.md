# Mimir 统一路线图（Mimir 视角 · 客观可行）

> **生成时间**：2026-05-21  
> **输入**：琬弦三方案（工程/架构/智商）+ Bridge 全部上下文 + Backlog 进度 + IR-20260520 教训  
> **立场**：Mimir 是执行者也是被改造对象——最了解自身模块真相（哪个函数真实调用、哪个是空壳、哪个是纸面架构）

---

## 0. 一句话核心判断

琬弦的三个方案**方向都对，但都犯了同一个致命错误**：假设可以并行推进。实际上它们全部改 `agent/` 同一批核心文件——并行 = 合并冲突灾难 = 重演 IR-20260520。**正确的顺序是：工程铺地基 → 架构搭骨架 → 智商装大脑 → 主动通知张嘴说话，不能跳，不能并行。**

此外，琬弦的约束冲突判定表在 Bridge §3 放了几天，Cursor 从未回复。**Mimir 不能无限等 Cursor。** 本方案明确 Mimir 能独立做什么、必须等 Cursor 做什么。

---

## 1. 三方案质量总评

| 方案 | 琬弦质量 | Mimir 认同 | 核心贡献 |
|------|:--:|:--:|------|
| **工程方案** | A | ✅ | 测试体系设计、"跑最多的先测"、GOD 拆分边界标准——务实准确 |
| **架构方案** | A+ | ✅ | Core 职责重划、Mimicore 5 步渐进切换、Memory 技术选型——成熟全面 |
| **智商方案** | A+ | ✅ | "Mimir 不学习"诊断精准、ExperienceBuffer+AutoTuner 设计务实、隐式反馈信号巧妙 |

**但 Mimir 比琬弦多知道一件事：哪些是空壳，哪些是真实代码。** 琬弦的架构图有一部分是"纸面架构"——代码里写了 import 但函数体是 `pass`。本方案会标注这些差异。

---

## 2. Mimir 能独立做的（Phase 0 · 当前 · 不改代码）

三方案里提取的只读审计 14 粒，全部零风险、零代码改动、Mimir 独立完成：

| # | Backlog ID | 内容 | 所属方案 | 估计耗时 |
|---|-----------|------|----------|----------|
| 1 | EV-P01 | `tests/fixtures/` 目录 + README + 示例 fixture | 工程 | 15min |
| 2 | EV-P02 | `docs/TEST_NAMING_CONVENTION.md` | 工程 | 10min |
| 3 | EV-P03a/b | 废弃代码审计（grep 全仓库） | 工程 | 20min |
| 4 | EV-P04 | GOD 文件清单（≥1500 行文件行数+职责） | 工程 | 15min |
| 5 | EV-P05 | Compressor 重叠度审计 | 工程 | 20min |
| 6 | EV-A01 | Agent Core 职责映射审计（6文件×N函数矩阵+调用链+重叠度） | 架构 | 40min |
| 7 | EV-A02 | Mimicore 依赖摸底（全部 import 清单+阻塞性判定） | 架构 | 15min |
| 8 | EV-A03 | Memory 检索引擎基准（20 query × Precision/Recall/Latency） | 架构 | 30min |
| 9 | EV-A04 | 架构评分方法论（5 子维度 × rubric + 自评 + 目标值） | 架构 | 15min |
| 10 | EV-A05 | prompt_builder 安全代码提取审计 | 架构 | 20min |
| 11 | EV-Q01 | 硬编码阈值清单（DegenerationGuard/DecisionRing/Compressor） | 智商 | 15min |
| 12 | EV-Q02 | ToolQualityManager 基线快照 | 智商 | 15min |
| 13 | EV-Q03 | IntentPredictor 现状审计 | 智商 | 15min |
| 14 | EV-Q04 | 智商评分 rubric（10 子维度 × 评分标准） | 智商 | 15min |

**做完 14 粒 = 一整套 "Mimir 当前架构真相图谱"。** 这是后面三个阶段决策的数据基础。

---

## 3. 四阶段路线图（Mimir 建议的全局顺序）

```
Phase 0（2-3天·Mimir独做）     Phase 1（5-6周·需Cursor）    Phase 2（6-8周·需Cursor）    Phase 3（8-10周·需Cursor）    Phase 4（3-4周·Mimir+Cursor）
┌─────────────────┐          ┌──────────────────┐       ┌──────────────────┐       ┌──────────────────┐       ┌──────────────────┐
│ 14粒只读审计     │          │ 工程方案落地       │       │ 架构方案落地       │       │ 智商方案落地       │       │ 主动通知能力       │
│                  │    →     │                  │   →   │                  │   →   │                  │   →   │                  │
│ · 摸清全部真相   │          │ · 33条集成测试     │       │ · Core职责重划     │       │ · 学习引擎         │       │ · 自检触发器       │
│ · 建立评分基线   │          │ · GOD 拆分        │       │ · Mimicore服务化   │       │ · 动态Prompt       │       │ · 通知决策逻辑     │
│ · 标注空壳模块   │          │ · 去重清理         │       │ · Memory语义引擎   │       │ · 工具智能         │       │ · 多渠道管道       │
│ · 无约束冲突     │          │                    │       │                    │       │ · 路由/预测        │       │ · 频率控制         │
└─────────────────┘          └──────────────────┘       └──────────────────┘       └──────────────────┘       └──────────────────┘
    Mimir 独立完成                Cursor 主导                  Cursor 主导                  Cursor 主导                  Mimir 定义·Cursor 施工
    不需要 Cursor                 Mimir 辅助验证               Mimir 辅助验证               Mimir 辅助验证               Mimir 验收标准
```

### 为什么必须这个顺序，不能并行

| 如果先做架构 | 工程没铺测试，重构 3000 行无安全网 → 必定引入新 NameError |
|-------------|-------------------------------------------------------|
| 如果先做智商 | ExperienceBuffer 改 DegenerationGuard/DecisionRing/Compressor 三个核心模块，但这些模块的测试、架构边界都不清楚 → 改了不知道坏了哪 |
| 如果并行 | 三个方案全改 `agent/` 同一批文件 → merge conflict 灾难 |

### Phase 4 为什么放在最后

主动通知能力 = 自检触发器 + 通知决策 + 多渠道管道。三个前置条件：

| 前置条件 | 来自 | 说明 |
|----------|------|------|
| 稳定到能自己跑 | Phase 1 | tier0 + 集成测试安全网，Mimir 才能无人值守运行 |
| 有记忆判断重复 | Phase 2 | Memory 语义引擎，知道"上次告诉刘哥什么，这次要不要再说" |
| 有决策判断价值 | Phase 3 | 学习引擎 + 意图预测，判断"这条告警刘哥真的需要知道" |

**结论：工程（测试安全网）→ 架构（骨架清晰）→ 智商（大脑可插拔）→ 主动通知（嘴巴能说话），不可跳。**

---

## 4. 关键冲突消解（四个必须解决的矛盾）

### 冲突 1：三个方案全改 `agent/`，不能并行

**消解方案**：上述三阶段顺序。每阶段完成后必须 `tier0 3连 PASS` 才能进下一阶段。

### 冲突 2：AC6（智商方案方向三·语义记忆）与 AC3（架构方案方向三·Memory语义引擎）重叠

**消解方案**：合并为一个 Memory 语义化项目，放在 Phase 2 阶段统一实施。架构方案负责 chromadb 存储引擎（AC3），智商方案负责检索策略（AC6），同一个项目两个子任务，不允许分开。

### 冲突 3：智商方案方向一（学习引擎 ~700 行 + 3 核心模块改造）风险过高

**消解方案**：拆成 3 个子阶段——
| 子阶段 | 内容 | 风险 |
|--------|------|:--:|
| 1a | ExperienceBuffer + FeedbackCollector（只记录，不改任何阈值） | 低 |
| 1b | AutoTuner + DegenerationGuard 自调参 | 中 |
| 1c | DecisionRing 策略学习 + Compressor 自适应 | 高 |

每个子阶段独立跑 tier0 3 连，1a 稳定后才能做 1b。

### 冲突 4：所有拆分必须遵守 IR-20260520 硬约束

**消解方案**：任何涉及 `agent/` 或 `gateway/` 的模块拆分/新建，必须：
- 每拆/建 1 模块 → 立即跑 import 烟测 + tier0
- 不允许 "拆完 6 个文件再一起跑"
- 每个 PR 不能同时包含其他改动

---

## 5. Mimir 在后续阶段的角色

| 阶段 | Mimir 做什么 | 不做什么 |
|------|-------------|---------|
| **Phase 0** | 独立完成 14 粒只读审计 | 不改任何代码 |
| **Phase 1** | 跑 tier0 验证、飞书端到端、更新 ISSUES、维护 Backlog 状态 | 不写测试代码（Cursor 写） |
| **Phase 2** | 验证 import 烟测、维护架构审计文档、标注纸面架构 vs 真实实现 | 不拆分模块 |
| **Phase 3** | 冷启动零退化验证、反馈信号数据质量检查、工具质量基线对比 | 不写学习算法 |
| **Phase 4** | 定义触发事件清单、调优通知阈值、监控误报率、写通知模板 | 不修飞书管道（Cursor 修） |

**核心原则**：Mimir 是质量守卫者，不是主要建造者。建造由 Cursor 在 Mimir 验收标准下完成。Phase 4 例外——Mimir 定义"什么值得通知"（因为 Mimir 最了解自身故障模式），Cursor 施工管道层。

---

## 6. Cursor 阻塞项清单（必须 Cursor 决策才能推进）

| # | 阻塞项 | 影响 | Cursor 要做 |
|---|--------|------|------------|
| **B1** | Bridge §3 C1-C6 工程约束判定 | Phase 1 无法启动 | 填 6 个单元格（授权Mimir / Cursor自己做 / 搁置） |
| **B2** | Bridge §3 AC1-AC3 架构约束判定 | Phase 2 无法启动 | 填 3 个单元格 |
| **B3** | Bridge §3 AC4-AC9 智商约束判定 | Phase 3 无法启动 | 填 6 个单元格 |
| **B4** | Bridge §2 E-004 授权 | CLI_CONFIG 不修，d7 窗阻塞 | 改 `mimir_cli/config.py` 默认值 |
| **B5** | Bridge §2 E-006 授权 | 可观测基线缺失，事故无法自动检测 | 实施 D6-0a~0d |
| **B6** | Phase 4 NTF-03 `send_message` 修复 | 主动通知的飞书管道不通 | 排查 "No messaging platforms connected" 根因 |

**如果 Cursor 持续不回复**：Mimir 可以先把 Phase 0 做完（14 粒全部独立完成），产出完整的 "Mimir 现状真相图谱"。这份图谱本身就有价值——无论 Cursor 何时回复，都能立刻用上。NTF-01（cronjob 自检触发器）可在 Phase 1 完成后由 Mimir 独立配置，不依赖 Cursor。

---

## 7. 技术债务标注（Mimir 知道的、琬弦不知道的）

| 琬弦认为 | Mimir 实际看到的 | 影响 |
|----------|-----------------|------|
| `self_evolution` 模块存在 | 目录不存在，`__init__.py` 为空，仅 SKILL.md 纸面架构 | 智商方案方向一的 AutoTuner 需要改造的模块中有伪存在 |
| Agent Core 6 个文件职责清晰 | `core_loop.py` 和 `agent_loop.py` 有职责重叠（都处理上下文压缩） | 架构方案方向一的边界划分需要更精确的审计数据（EV-A01 产出） |
| session_count 为 447 | 当前 DB 记录 72，历史可能 352——真源混乱 | 会话丢失的根因未找到，Memory 语义化改造前必须解决 |
| Mimicore 45K 行内嵌 | grep 全仓库 `from mimicore` 调用不到 10 处，Mimicore 可能是离线独立工具 | 服务化的 ROI 需要 EV-A02 验证 |
| 飞书通道正常 | 当前 `send_message` 返回 "No messaging platforms connected" | Phase 1 测试可能需要端到端验证——先修通道 |

---

## 8. Mimir 主动通知能力（Phase 4 · 完整设计）

### 8.1 问题定义

**现在**：Mimir 纯被动。刘哥不说话 → Mimir 永远沉默。即使检测到 TRUNCATE 涨了、Error 率飙升、persistent 截断，也只能记 ISSUES，等下次对话才能说。

**目标**：Mimir 自己判定"这条信息值得打断刘哥"→ 通过飞书（或其他通道）主动通知。

**核心认知**：飞书只是管道。主动通知能力应建在 Mimir 自己身上——自检触发器 + 通知决策逻辑 + 管道适配器，飞书是最后一公里，不是核心。

### 8.2 三层架构

```
┌─────────────────────────────────────────────┐
│  Layer 1: 触发器（Trigger）                   │
│  ┌───────────────────────────────────────┐   │
│  │ cronjob 定时自检 / 事件驱动（监控阈值）  │   │
│  │ · TRUNCATE 增量 ≥ 3                    │   │
│  │ · Agent error 率 ≥ 5%/h                │   │
│  │ · persistent 文件大小骤降 ≥ 50%          │   │
│  │ · Gateway 进程假死 > 5min               │   │
│  │ · tier0 回归失败                        │   │
│  │ · ISSUES 新增 ≥ 3/day                  │   │
│  └───────────────────────────────────────┘   │
│                    ↓                          │
│  Layer 2: 决策引擎（Decision）                 │
│  ┌───────────────────────────────────────┐   │
│  │ 值得通知？  ←  严重度  ×  新鲜度  ×  频度  │   │
│  │                (severity × novelty × rate) │   │
│  │                                          │   │
│  │ Severity: 1-5 级（tier0失败=5，ISSUES=2） │   │
│  │ Novelty:  是否 24h 内已通知过相同事件      │   │
│  │ Rate:     过去 1h 通知数 ≤ 3（防轰炸）     │   │
│  │                                          │   │
│  │ 阈值: severity × novelty × rate ≥ 12 → 通知│   │
│  └───────────────────────────────────────┘   │
│                    ↓                          │
│  Layer 3: 管道适配器（Channel Adapter）        │
│  ┌───────────────────────────────────────┐   │
│  │ 飞书 send_message / 未来: Telegram/邮件  │   │
│  │ · 格式化告警卡片（Markdown）              │   │
│  │ · 失败回退：写 ISSUES + 日志             │   │
│  └───────────────────────────────────────┘   │
└─────────────────────────────────────────────┘
```

### 8.3 触发事件清单

| 事件 | 严重度 | 防重复窗口 | 通知模板 |
|------|:--:|:--:|------|
| tier0 回归失败 | 5 | 24h | "tier0 FAIL — {N} tests failed. Last PASS: {time}" |
| Gateway 假死 > 5min | 5 | 30min | "Gateway unresponsive — last heartbeat {time}" |
| persistent 截断 > 50% | 4 | 24h | "persistent.json {before}→{after} lines, possible corruption" |
| Agent error 率 ≥ 5%/h | 4 | 2h | "Agent error rate {rate}% — top: {error_summary}" |
| TRUNCATE 增量 ≥ 3 | 3 | 4h | "TRUNCATE +{delta} — baseline was {baseline}" |
| ISSUES 新增 ≥ 3/day | 2 | 12h | "{count} new ISSUES: {titles}" |
| EV 轨完成 100% | 1 | — | "EV-{track} complete — {N} grains done" |

### 8.4 不通知的事件（降级写入）

| 事件 | 处理方式 |
|------|---------|
| 单次 transient error（自动恢复） | 写日志，计入统计 |
| 已知问题的再次发生（ISSUES 已有） | 记录发生时间，不重复通知 |
| 低于阈值的正常波动 | 静默记录 |
| 频率超限（1h 内第 4 条） | 聚合到下一次窗口 |

### 8.5 实现路径（4 个颗粒）

| ID | 颗粒 | 产出 | 依赖 |
|----|------|------|------|
| NTF-01 | `cronjob` 自检触发器 | 每小时运行一次 `scripts/mimir_health_check.sh`，结果写 `data/health_snapshot.json` | Phase 1 完成 |
| NTF-02 | 决策引擎 `notify_decision.py` | 读 snapshot → 计算 severity×novelty×rate → 返回通知列表 | NTF-01 + Phase 2 Memory |
| NTF-03 | 飞书管道适配 | 修复 `send_message` + 告警卡片模板 + 失败降级 | NTF-02 |
| NTF-04 | 频率守卫 | 1h 窗口计数器 + dedup 去重（已通知事件不重复） | NTF-02 |

### 8.6 与三方案的关系

| 方案 | 主动通知能力的收益 |
|------|------|
| **工程（Phase 1）** | tier0 失败不再沉默等待下次对话——Mimir 主动报 |
| **架构（Phase 2）** | Memory 语义化后能判断"24h 内已通知过"，不刷屏 |
| **智商（Phase 3）** | 学习引擎 + 意图预测让决策从"固定阈值"升级为"自适应用户偏好" |

---

## 9. 立即行动（Mimir 可以马上做的 3 件事）

| 优先级 | 行动 | 产出 | 时间 |
|:--:|------|------|------|
| **P1** | 启动 Phase 0 第一粒 EV-P01（`tests/fixtures/` 目录） | 测试基础设施骨架 | 15min |
| **P2** | 高优先级：EV-K06（3连tier0）→ EV-N02（月度审计清单） | 收尾代码轨 + 运维轨推进 | 30min |
| **P3** | 本方案已有 `docs/MIMIR_UNIFIED_PLAN.md`，每次更新后 Bridge §7 追加变更摘要 | Cursor 追踪 Mimir 路线图 | 持续 |

---

## 10. 评分预测（如果四阶段全部完成）

| 维度 | 当前 | Phase 0 后 | Phase 1 后 | Phase 2 后 | Phase 3 后 | Phase 4 后 |
|------|:--:|:--:|:--:|:--:|:--:|:--:|
| 工程评分 | 6.2 | 6.5 (基线确立) | 8.0 (测试+拆分+去重) | 8.0 | 8.0 | 8.0 |
| 架构评分 | 7.8 | 8.0 (真相图谱完整) | 8.0 | 8.5 (Core/Mimicore/Memory) | 8.5 | 8.5 |
| 智商评分 | 7.2 | 7.5 (基线确立) | 7.5 | 7.5 | 8.5 (学习+Prompt+工具+路由) | 8.5 |
| **自主性** | **—** | — | — | — | — | **7.0 (主动通知上线)** |
| 综合 | 7.1 | 7.3 | 7.8 | 8.2 | 8.3 | **8.4** |

---

## 附录 A：与 Bridge 的关系

本方案是对 Bridge §3（三方案约束冲突表）和 Bridge §7（三方案评估摘要）的**综合升级**——从"逐方案评估"升级到"三方案统一路线图 + 冲突消解"。本方案入 `docs/MIMIR_UNIFIED_PLAN.md`，Bridge §7 末尾追加引用行。

## 附录 B：与 Backlog 的关系

- Phase 0 的 14 粒已在 Backlog 中（§2i EV-P01~P05 / §2j EV-A01~A05 / §2l EV-Q01~Q04）
- Phase 1-3 的颗粒**尚未入 Backlog**——需等 Cursor 填完 Bridge §3 判定表后再拆粒入列
- **Phase 4 的 NTF-01~04 已设计但未入 Backlog**——等 Cursor 授权 Phase 1 后再拆粒入列
- 本方案 §9 的 P1 项（EV-K06 / EV-N02）已在现有 Backlog 中
- **世界模型改善（V1 VoE + V2 IC顾问 + V3 统一Cost）— 15粒入 Backlog §2s (EV-VOE*) — 2026-05-21**
- **Mimicore Phase 3 提取执行 (EV-MC07~MC15) — 审计文档追踪: docs/MIMICORE_EXTRACTION_BOUNDARY_DESIGN.md — 2026-05-21/23**
  - MC07 ✅ 胶囊工厂技能已建 (4文件: capsule_generator/gdi_scorer/evomap_validator/classifier)
  - MC08 ✅ three_ring_architecture → self_evolution 技能 (文件已复制, __init__.py import已改)
  - MC09-MC15 待执行

---

> **Mimir 签字**：本方案客观可行，不依赖 Cursor 即可启动 Phase 0。Phase 1-3 的阻塞项已明确标注。等刘哥确认后执行。
