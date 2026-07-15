# mimiraether-study-tree

MimirAether 知识研究树——对外部技术的调研、对比、吸收结论。

## 使用方式

每次研究一个新项目后，在此记录研究结论，并标记状态 `[x]`。
研究成果树是"已消化、已决策"的知识，不是 backlog 执行清单。

## 重要路径真相
- WM surprise_events: ~/.mimiraether/data/wm_phase0/surprise_events.jsonl（1497行，99.9%工具预测偏差）
- 不要把这个数据和 key_decisions/learned_patterns 混淆——后者是蒸馏后的高质量条目
- cron job 持久化文件可能在 Gateway 重启后丢失，依赖 session 内注册而非磁盘持久

## 研究树

### #1 SkillSpector — ✅ [x]
- **来源**: NVIDIA 开源，9,513 stars
- **功能**: 安全扫描 AI agent skills（检测提示注入、数据窃取、供应链攻击）
- **结论**: skills_qa.py（1,031行，已接入skill_curator）覆盖了自写 skill 质量保障的所有需要。SkillSpector 针对外来 .py 可执行技能，我们是自写 .md 技能。**不引入**。

### #2 CowAgent 自进化 — ✅ [x]
- **来源**: zhayujie，45,570 stars，中文 trending #1
- **功能**: 多模型、多平台、自进化 agent，从 chatgpt-on-wechat 进化而来
- **5层对比**:
  | 层 | CowAgent | MimirAether | 差距 |
  |:-:|----------|-------------|:----:|
  | L1 记忆维护 | 自动写MEMORY.md + 知识库主题组织 | memory 工具写入 persistent.json | 缺主题知识库 |
  | L2 上下文总结 | 超限时工具截断+轮次裁剪+注入总结 | context_compressor 884行 | 基本持平，CowAgent裁剪稍好 |
  | L3 会话后复盘 | 改技能+收尾未完成任务+补齐记忆 | skill_curator + 守卫复盘 | 缺收尾未完成任务 |
  | L4 梦境记忆蒸馏 | **每天23:55定时**：读所有记忆→去重→蒸馏→写日记→≤50条 | **agent/dream_memory.py 已上线 + cron 23:00** | ✅ 已解决 |
  | L5 源码自更新 | cow self-restart + 自检 + 接力进程 | systemd 自启(可崩溃恢复) | 持平 |
- **梦境蒸馏已落地**（2026-06-23）: agent/dream_memory.py 276行 + scripts/dream_memory_cron.sh + cron 每日 23:00

### #3 Agent-Reach — ✅ [x]（安装完成，但搜索仍走 Tavily）
- **来源**: Panniantong，38,139 stars（2026-06-10）
- **功能**: 13 平台零 API 费搜索/阅读
- **安装**: `~/.agent-reach-venv/` + `~/.mimiraether/bin/agent-reach`（Mimir 专属副本）
- **可用渠道**: GitHub(gh CLI)、YouTube(yt-dlp)、B站(REST)、RSS —— 6/13 激活
- **不可用**: Jina Reader(r.jina.ai)被防火墙阻断、Exa MCP 未配置
- **注意**: `web_search`/`web_extract` 仍走 Tavily Gateway 基础设施，未切换到 Agent-Reach。Tavily 当前可用（key 已加 .env + 重启后生效）

### #4 Codebase-Memory-MCP — ✅ 跳过
- **来源**: DeusData，12,034 stars
- **功能**: 使用 MCP 协议的代码知识图谱持久化
- **结论**: OC-04 审计决定保持现状。**跳过**。

### #5 百度千帆搜索 — ⏸ PENDING · 等待触发条件
- **来源**: Evilran/baidu-mcp-server（MIT, 886行）
- **安装状态**: `pip install baidu-mcp-server` 已装，mcporter 配置 `baidu-search` 已注册
- **现状**: curl_cffi 爬虫模式，被百度反爬拦截，返回空
- **淘汰选择**: Docker 版 baidu-ai-search（Playwright 浏览器池）可绕过反爬，但需运维 Docker 容器
- **结论**: 当前搜索需求已由 Tavily(恢复) 覆盖。**不装 Docker 版。标记 PENDING。** 触发条件：出现 Tavily 搜不到的中文独占内容且必须知道时再装。

### #6 PMD / SkeMex 论文 — ⏸ PENDING · 搜索工具恢复后深读
- PMD（Procedural Memory Distillation, Salesforce 2026）: 三级记忆架构 (Experience→Insight→Behavior) 与我们的梦境蒸馏框架高度同构
- SkeMex: Read-Write-Assess-Govern 闭环，填补梦境蒸馏的"效用评估"缺失环节
- 结论: 等待 Tavily 恢复稳定后再拉全文深读

### #7 Superpowers — ✅ 已吸收

**来源**: obra/superpowers，**252K stars**（2026-07-15 #1 trending）
**核心**: 13 skill 组成的完整 SDLC 方法论（brainstorming → worktrees → 写 plan → 执行 → TDD → review → 收尾）
**许可**: MIT
**核心哲学**: Test-Driven Development / Systematic over ad-hoc / Complexity reduction / Evidence over claims

#### 全 13 Skill 交叉对比

| # | Superpowers Skill | 我们有吗 | 质量对比 | △ |
|:-:|:-----------------|:--------:|:--------|:-:|
| 1 | **brainstorming** | ✅ `mimiraether-brainstorming` | 我们有基础版本。他们：9步清单 + anti-pattern + visual companion。**差距：无强制门控、无 anti-pattern 章节、无 visual compaion** | 🟡 |
| 2 | **writing-plans** | ✅ `writing-plans` | 他们的：bite-sized 2-5min 任务粒度、标准 plan header 模板、placeholder 禁止、"No Placeholders → plan 失败"规则。**差距：模板不够精确、缺对 TBD/TODO 的硬禁止** | 🟡 |
| 3 | **executing-plans** | ✅ `executing-plans` | 大致持平。他们的在 checkpoint 点更精确 | 🟢 |
| 4 | **verification-before-completion** | ✅ `mimiraether-verification`（auto_load）| **我们有的就是抄他们的。差距：缺 rationalization prevention 表格** | 🟢 |
| 5 | **subagent-driven-development** | ✅ `delegate-subagent` + `subagent-driven-development` | 他们的：2-stage review（spec compliance → code quality）、4种 implementer status（DONE/DONE_WITH_CONCERNS/NEEDS_CONTEXT/BLOCKED）、explicit model selection。**差距：无完整 4 种状态处理流程** | 🟡 |
| 6 | **test-driven-development** | ✅ `test-driven-development` | 他们的：铁律"NO PRODUCTION CODE WITHOUT FAILING TEST FIRST"、regression 验证明文要求。我们基本持平 | 🟢 |
| 7 | **finishing-a-development-branch** | ✅ `finishing-a-development-branch` | 他们的：6 步精确流程、环境检测区分 3/4 菜单。**差距：无环境检测步骤** | 🟡 |
| 8 | **using-git-worktrees** | ✅ `using-git-worktrees` | 他们的：Step 0 检测（含 submodule guard！）、native tool 优先。**差距：无 submodule guard** | 🟡 |
| 9 | **requesting-code-review** | ✅ `requesting-code-review` | 大致持平。他们的有 reviewer dispatch template。**差距：缺精确的 reviewer prompt 模板** | 🟢 |
| 10 | **systematic-debugging** | ✅ `mimiraether-root-cause-debugging` | 他们的：4-phase + 铁律"NO FIXES WITHOUT ROOT CAUSE" + **3次失败后架构边界**。**差距：缺"3+ fixes → STOP"规则** | 🟡 |
| 11 | **dispatching-parallel-agents** | ❌ **缺失** | 我们有 `delegate_task` 批量模式，但无专门的"并行调试"skill。**差距：新增 skill** | 🔴 |
| 12 | **receiving-code-review** | ❌ **缺失** | 我们是单向 review。他们：requesting + receiving 双向。**差距：新增 skill** | 🔴 |
| 13 | **writing-skills** | ✅ `mimiraether-skill-solidify` + `hermes-agent-skill-authoring` | 他们的：TDD for skills（写 test scenario → 先看 agent 无 skill 时失败 → 写 skill → 看 agent 匹配）。**差距：缺 TDD 式技能创作方法论** | 🟡 |

#### 吸收结论

| 差距级别 | 计数 | 行动 |
|:-------:|:----:|:----|
| 🔴 缺失 | 2 | 创建 `dispatching-parallel-agents` + `receiving-code-review` |
| 🟡 质量 | 7 | 升级 7 个同名 skill（加 anti-pattern / iron law / 精确模板） |
| 🟢 持平 | 4 | 维持现状（verification / TDD / code-review / executing-plans） |

#### 四个可以直接吸收的核心模式

1. **铁律机制** — 每个 skill 开头的"Iron Law"段落（如 "NO PRODUCTION CODE WITHOUT A FAILING TEST FIRST"）是很强的行为约束模式。我们每个 skill 也应该有
2. **Anti-patterns** — 每个 skill 都列出"跳过技能的常见借口"并配套"reality"反驳。我们从 Superpowers 的 verification 技能直接抄了 rationalization prevention 表，应该在所有 skill 里推广
3. **Red Flags** — "如果你在想 X → STOP"的模式比模糊警告更有效
4. **Evicende over claims** — 贯穿全体技能的核心哲学

### #8 mattpocock/skills — ✅ 已吸收

**来源**: mattpocock/skills，**165K stars**（2026 trend）
**核心**: 10+ 工程技能（user-invoked + model-invoked 两种模式）
**许可**: MIT
**哲学**: 小型、可组合、易适配的技能 vs 大而全的框架

#### 可吸收的部分

| 他们的 skill | 我们缺吗 | 建议 |
|:-----------|:--------:|:-----|
| **`/grill-me`** / **`/grill-with-docs`** | ⚠️ 部分 | 结构化质询流程——先问清楚需求再动手。我们 brainstorming 有但不够结构化。可吸收"garilling session"模式 |
| **`/improve-codebase-architecture`** | ✅ 缺 | HTML 报告 + 每日架构扫描。我们自己应该在 skills 质量层做类似的 |
| **`/to-spec`** | ✅ 缺 | 通过质询探索模块边界再写 spec。可吸收 |
| **CONTEXT.md + 共享语言** | ⚠️ 部分 | 我们 memory 了但没有"项目级共享术语"文档。他推荐 /grill-with-docs 自动构建 |
| **skills.sh 可编辑安装** | ❌ 不适应 | 我们技能直接写盘，不需要 |

**结论**: 主要吸收 `grill-with-docs` 方法论（结构化质询 + 共享术语自动生成）和 `/improve-codebase-architecture`（技能质量扫描报告）。不复制全项目。

### #9 TencentDB-Agent-Memory — ✅ 已吸收

**来源**: TencentCloud/TencentDB-Agent-Memory，**8.5K stars**（2026-07 #1 trending）
**核心**: 4层渐进式记忆流水线（L0-L3）+ 符号化短期记忆
**许可**: MIT
**语言**: TypeScript（84%）

#### 架构要点

| 层 | 名称 | 内容 | 格式 | 与我们对比 |
|:-:|:----|:-----|:----|:----------|
| L0 | Conversation | 原始对话 | 无结构化 | ✅ 我们也有 |
| L1 | Atom | 原子事实 | JSONL（SQLite 全文检索） | ⚠️ 类似我们的 key_decisions |
| L2 | Scenario | 场景块 | Markdown（人类可读） | ❌ 我们没有 |
| L3 | Persona | 用户画像 | Markdown（persona.md） | ✅ 类似我们的 memory user 存储 |
| Short-term | Mermaid Canvas | 符号化工具日志 | Mermaid graph + node_id 引用 | ❌ **我们没有** |

#### 与我们持久化系统的对比

| 维度 | TencentDB | 我们（persistent.json） |
|:----|:---------|:----------------------|
| 层数 | 4 | 2（kd + lp，无 L2/L3 中间层）|
| 检索 | SQLite + sqlite-vec（混合关键词+向量 RRF） | 纯关键词（read_file） |
| 短期记忆 | Mermaid 符号化 + refs/*.md 脱载 | 无短期层 |
| 用户画像 | persona.md（自动生成，每 50 记忆更新） | memory 工具用户存储（手动）|
| 集成 | OpenClaw 插件 + Hermes Docker | 自有 Gateway |
| Token 节省 | −61%（221M→85M） | 无测量 |

#### 可吸收的方向（非复制，是参考）

1. **Mermaid Canvas 短期记忆符号化** — 我们蒸馏的 kd/lp 是纯文本，TencentDB 用 Mermaid 图高度压缩。可在蒸馏输出中引入符号化摘要
2. **L2 Scenario 层** — 我们在 persistent.json 只有 kd/lp 两层平坦结构。加一个"场景"层可按对话主题组织，检索效率更高
3. **persona.md 自动生成** — 我们 memory 工具的用户存储是手动的。可参考 TencentDB 的自动 persona 生成（每 50 记忆一次）
4. **混合检索（BM25+向量）** — 当前检索全靠 `grep -r` / `read_file`。引入 sqlite-vec（完全本地，无外部 API）可大幅提升 recall

**结论**: 不复制项目（TypeScript，异构架构）。但 L2 场景层 + Mermaid 符号化 + 混合检索的方向值得在 persistent.json v2 中参考。**标记为 P1 候选参考**。

### #10 Self-Harness 论文 — ✅ 已吸收

| 论文 | 日期 | 核心 | 与我们关系 |
|:----|:----|:-----|:----------|
| **Self-Harness** (arXiv:2606.09498) | Jun 8 | 三阶段：Weakness Mining → Harness Proposal → Validation。最高 +60% | **蒸馏16轮修复是手动 Self-Harness。下一步：自动化三阶段循环** |
| **Meta-Harness** (arXiv:2603.28052) | Mar | 外环系统自动搜索 harness 代码。+7.7 分 | 可参考外环收敛模式 |
| **Agent Harness Survey** (2026) | Apr | 形式化定义 H=(E,T,C,S,L,V)。harness 是生产瓶颈 | 验证我们的架构（6 组件全有但缺形式化评估） |

#### Self-Harness 三阶段 vs 已做

| Self-Harness 阶段 | 我们手动做了什么 | 自动化差距 |
|:-----------------|:---------------|:----------|
| Weakness Mining | 16 轮失败 → 发现 `***`、`.bak→main`、缓存覆盖 | 当前靠你手动发现问题 |
| Harness Proposal | 哨兵文件 `.distilled`、`provider_registry` 回退 | 我提出方案但需你验证 |
| Validation | 3 路交叉验证 + 读盘确认 | 当前已有 verification 技能，但未接回全循环 |

**结论**: Self-Harness 已经是我们实际在做但没有形式化命名的方法论。**P0 吸收项**：

1. 在三阶段已手动跑通过的基础上，通过 `self_evolution` 技能实现 Weakness Mining 的半自动化（日志异常检测 → 自动提案 → 回归测试 → 通知你）
2. 不复制论文全貌，只吸收三阶段循环结构

## 长期差距记录

| 优先级 | 差距 | 来源 | 状态 |
|:-----:|------|:----:|:----:|
| P0 | L4 梦境记忆蒸馏 | CowAgent L4 | ✅ [x] agent/dream_memory.py + cron 已修复 |
| P0 | Self-Harness 自动化 | #10 Self-Harness 论文 | ⏸ 手动跑通过，待半自动化 |
| P1 | 搜索替代 | Tavily 恢复 | ✅ [x] Tavily key 已生效；Agent-Reach 备用已装 |
| P1 | TencentDB 记忆架构参考（L2场景层+Mermaid符号化+混合检索） | #9 TencentDB | ⏸ P1 候选参考 |
| P1 | Skill 质量升级（7 🟡 + 2 🔴 缺失） | #7 Superpowers | 🔄 需按 △差距表推进 |
| P2 | 百度搜索（中文独占内容） | 百度反爬 | ⏸ PENDING 等待触发条件 |
