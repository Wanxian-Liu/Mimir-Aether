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

#### Self-Harness 自动化 — ⏸ PENDING（2026-07-15）

**决策依据（CLAUDE.md §2 Simplicity First）:**
- 当前只有 1 个真实失败模式（蒸馏 16 轮 — 已修复，哨兵机制已落地）
- n=1 时建自动化系统 → 过度拟合。等积累 ≥3 种不同失败模式后再启动自动化
- 自然积累路径：`verification` skill auto_load 持续工作 → 3-5 次会话自然积累失败模式 → 第 5 次会话后评估是否达到 ≥3 种

**前置条件:**
- [ ] 积累 ≥3 种不同的真实失败模式（来自 verification 自检记录）
- [ ] 每种失败模式有明确的 Weakness Mining 路径（日志/文件/断言）
- [ ] 回归测试集覆盖已累积的所有模式

**不排期。等条件自然触发。**

### #11 addyosmani/agent-skills — ✅ 已吸收（2026-07-15）

**来源**: Addy Osmani（前 Google Director, Gemini/Cloud AI），**78K stars**，MIT
**核心**: 24 个结构化 workflow skill + 8 个 slash command，覆盖完整 SDLC

#### 项目结构

```
agent-skills/
├── skills/          # 24 skills (23 生命周期 + 1 meta)
│   ├── using-agent-skills/      # Meta — 路由用户意图到正确 skill
│   ├── interview-me/            # Define
│   ├── idea-refine/             # Define
│   ├── spec-driven-development/  # Define
│   ├── planning-and-task-breakdown/ # Plan
│   ├── incremental-implementation/  # Build
│   ├── context-engineering/      # Build
│   ├── source-driven-development/  # Build
│   ├── doubt-driven-development/  # Build
│   ├── frontend-ui-engineering/   # Build
│   ├── test-driven-development/   # Build
│   ├── api-and-interface-design/  # Build
│   ├── browser-testing-with-devtools/  # Verify
│   ├── debugging-and-error-recovery/  # Verify
│   ├── code-review-and-quality/   # Review
│   ├── code-simplification/       # Review
│   ├── security-and-hardening/    # Review
│   ├── performance-optimization/  # Review
│   ├── git-workflow-and-versioning/  # Ship
│   ├── ci-cd-and-automation/      # Ship
│   ├── deprecation-and-migration/  # Ship
│   ├── documentation-and-adrs/     # Ship
│   ├── observability-and-instrumentation/ # Ship
│   └── shipping-and-launch/       # Ship
├── agents/          # 4 specialist personas
├── references/      # 7 reference checklists
├── hooks/           # Session lifecycle hooks
├── .claude/commands/  # 8 slash commands (Claude Code)
├── .gemini/commands/  # 8 slash commands (Gemini CLI)
├── commands/          # 8 slash commands (Antigravity CLI)
└── docs/              # Setup guides per tool
```

#### 8 个 Slash Command

| Command | Phase | What it does |
|:--------|:-----|:-------------|
| `/spec` | Define | Spec before code |
| `/plan` | Plan | Small atomic tasks |
| `/build` | Build | One slice at a time |
| `/test` | Verify | Tests are proof |
| `/review` | Review | Improve code health |
| `/webperf` | Review | Measure before optimize |
| `/code-simplify` | Review | Clarity over cleverness |
| `/ship` | Ship | Faster is safer |

#### 5 个核心哲学（全部可吸收）

| # | 哲学 | 含义 | 我们有吗 |
|:-:|:----|:-----|:--------:|
| 1 | **Process over prose** | Skill 是 workflow（步骤+检查点+退出标准），不是参考文档。每一段话都对应 agent 可执行的行动 | ⚠️ 部分。我们已有但不够结构化 |
| 2 | **Anti-rationalization tables** | 每个 skill 开头有"常见借口 vs 现实"表格。LLM 擅长自圆其说——预写反驳让借口无法藏身。**这是最可吸收的模式** | ❌ 只有 verification 有，其他 31 个 skill 没有 |
| 3 | **Verification is non-negotiable** | 每个 skill 以**具体可验证的证据**终止（测试通过/构建输出/runtime trace/评审签名）。"Seems right"不够 | ✅ 我们 verification skill 已有，但未普及到所有 skill |
| 4 | **Progressive disclosure** | Meta-skill 只加载相关技能，不全部注入。20-skill 库压到 ~5K tokens | ❌ 我们 32 个 skill 全部 auto_load 或带触发词，无路由层 |
| 5 | **Scope discipline** | "只碰你被要求碰的东西"。他们的 meta-skill 硬编码这个规则 | ⚠️ 我们 CLAUDE.md §3 有 Surgical Changes，但无 skill 层强制 |

#### 交叉对比：他们有的 vs 我们有的

| # | 他们的 skill | 我们有吗 | 对比 | 差距 |
|:-:|:-----------|:--------:|:----|:---:|
| 1 | **using-agent-skills**（Meta） | ❌ **缺失** | 32 个 skill 但无路由层。用户说"修这个 bug"时我不知道该加载哪个 skill | 🔴 P0 |
| 2 | **interview-me** | ❌ 缺类似物 | 一次一问直到 95% 信心。比 brainstorming（我们只有发散无收敛）更精确 | 🟡 P1 |
| 3 | **idea-refine** | ⚠️ brainstorming | 我们的发散→收敛程度不够。缺"3 个方向→评分→选择"流程 | 🟡 P1 |
| 4 | **spec-driven-development** | ⚠️ writing-plans | 更正式：spec 先于代码。纯文本概要写 5 行也有效 | 🟡 P1 |
| 5 | **planning-and-task-breakdown** | ✅ writing-plans + executing-plans | 大致持平 | 🟢 |
| 6 | **incremental-implementation** | ✅ executing-plans | 他们的有垂直切片概念，我们更模块化 | 🟢 |
| 7 | **context-engineering** | ⚠️ context-compressor | 不同概念：他们的是"为当前任务构建最佳上下文"，我们是"压缩长对话"。互补 | 🟡 P2 |
| 8 | **source-driven-development** | ❌ 缺类似物 | "Always work from a source of truth" — 文档/设计文档/API spec 是真源，代码是实现 | 🟡 P2 |
| 9 | **doubt-driven-development** | ❌ 缺类似物 | "在实现前问什么东西可能会出问题" — 风险预检 | 🟡 P1 |
| 10 | **test-driven-development** | ✅ | 我们已有 + auto_load | 🟢 |
| 11 | **code-review-and-quality** | ✅ | 我们已有 requesting + receiving | 🟢 |
| 12 | **code-simplification** | ❌ 缺类似物 | YAGNI review + Chesterton's Fence（不要删你理解不了的东西）| 🟡 P1 |
| 13 | **security-and-hardening** | ❌ 缺类似物 | 安全审查 checklist（注入/XSS/权限/密钥管理）| 🟡 P1 |
| 14 | **performance-optimization** | ❌ 缺类似物 | 性能审查（加载/渲染/网络/内存）| 🟡 P2 |
| 15 | **debugging-and-error-recovery** | ✅ root-cause-debugging | 方向一致。他们的缺"3次失败→架构边界"规则（我们有）| 🟢 |
| 16 | **git-workflow-and-versioning** | ✅ using-git-worktrees | 持平 | 🟢 |
| 17 | **ci-cd-and-automation** | ❌ 缺类似物 | CI/CD pipeline 自动化 workflow | 🟡 P2 |
| 18 | **shipping-and-launch** | ✅ finishing-a-development-branch | 持平 | 🟢 |
| 19 | **documentation-and-adrs** | ❌ 缺类似物 | ADR 写作 + 文档更新 workflow | 🟡 P2 |
| 20 | **observability-and-instrumentation** | ❌ 缺类似物 | 日志/监控/告警 | 🟡 P2 |
| 21 | **deprecation-and-migration** | ❌ 缺类似物 | 弃用/迁移流程 | 🟡 P2 |
| 22 | **api-and-interface-design** | ❌ 缺类似物 | API 设计 review | 🟡 P2 |
| 23 | **browser-testing-with-devtools** | ❌ 不适应 | 前端专用，跳过 | — |
| 24 | **frontend-ui-engineering** | ❌ 不适应 | 前端专用，跳过 | — |

#### 最大可吸收模式：Anti-rationalization tables

这是整个项目中唯一不能跳过的东西。原理：

> LLM 本质上是寻找理由的机器。它擅长为"为什么这次不需要写测试/写 spec/做 review"生成有说服力的段落。
> Anti-rationalization table 是**在撒谎发生前预写的反驳**。

他们的例子：

| 常见借口 | 反驳 |
|:--------|:-----|
| "这个任务简单到不需要 spec" | 验收标准仍然适用。5 行可以。0 行不行。|
| "我之后再写测试" | "之后"是最危险的词。先写会失败的测试。|
| "测试都过了，发吧" | 测试通过是证据，不是证明。检查 runtime、用户可见行为、人工 diff review。|

**我们要做的事情**：把 Anti-rationalization tables 植入每个现有的 skill。Skill 数 32 个×每 skill 2-3 个常见借口 = ~80 行总增量。

#### 吸收结论和行动

| 差距级别 | 计数 | 行动 |
|:-------:|:----:|:-----|
| 🔴 P0 缺失 | 1 | **创建 meta-skill `using-agent-skills`** — 用户意图→正确 skill 路由 |
| 🟡 P1 值得 | 5 | 创建 `interview-me`、`doubt-driven-development`、`code-simplification`、`security-and-hardening`、`spec-driven-development` |
| 🟡 P2 可做 | 8 | context-engineering、source-driven-development、performance-optimization、ci-cd、doc-adrs、observability、deprecation、api-design |
| 🟢 持平 | 6 | TDD、code-review、debugging、git-workflow、shipping、planning |
| — 跳过 | 2 | 前端专用（browser-testing、frontend-ui）|

#### 不需复制

- 不需要装 install 脚本——我们的 skill 直接写盘
- 不需要跨平台命令目录——我们只有 Feishu
- 不需要 specialist agent personas——我们没有多 agent 编排

#### 第一行动

创建 **`using-agent-skills`（meta-skill）** — 这是唯一能立即改善 32 个 skill 使用效率的改动。用户一说"修 bug" / "写代码" / "review PR"，自动知道该加载哪个具体 skill。

### #12 GDM AI Control Roadmap — ✅ 已吸收（2026-07-18）

**来源**: Google DeepMind，arXiv:2607.13087（2025/2026）
**核心**: AI Control 第二道防线 — 当 AI agent 不可信时，用系统级防御检测和阻止破坏。三阶段：Threat Model → Control Invariants → Mitigations。
**许可**: CC-BY 4.0

#### 三阶段架构

| 阶段 | 含义 | 与我们对应 |
|:----|:-----|:----------|
| **Threat Model** (TRAIT&R) | MITRE ATT&CK 衍生分类法，定义 attacker 目标（Loss of Control / Work Sabotage / Direct Harm）和 8 种战术 | ⚠️ 我们没有形式化威胁模型。tool-triggers §8 近似"防御规避"但不是完整分类 |
| **Control Invariants** | 不可协商的检测和预防目标 | ✅ 我们的 verification 技能四层 = 检测；哨兵机制 = 预防 |
| **Mitigation Ladder** (D1-D4 + R1-R3) | 7 层渐进式缓解措施，从 CoT monitoring 到 shutdown infrastructure | ⚠️ 我们有 D 层（detection）但缺 R 层（response）|

#### 6 种检测类型 vs 我们的验证层

| DeepMind 检测类型 | 我们有没有 | 差距 |
|:-----------------|:--------:|:----|
| **Alignment testing**（体外评估） | ✅ verification L1（Ralph tier0） | 持平 |
| **CoT monitoring**（推理链监控） | ❌ 没有 | **新增** — 蒸馏时检查 LLM 输出的推理过程 |
| **Action monitoring**（行为监控） | ⚠️ 部分 — verification L2（一致性检查）| 需强化 |
| **Activations monitoring**（内部状态监控） | ❌ 技术上无法做 | 跳过 |
| **PR monitoring**（代码审查） | ✅ requesting-code-review | 持平 |
| **Honeypots**（蜜罐检测） | ⚠️ 部分 — verification L4（自问清单）| 方向一致 |

#### 可吸收的模式

1. **度量指标** — DeepMind 用 Coverage / Recall / Time-to-response 衡量检测质量。我们当前验证只有 PASS/FAIL，没有量化指标
2. **R 层（响应）** — 我们只有 D（检测）没有 R（响应）。论文的 R1-R3（隔离→回滚→关闭）可吸收为 verification 失败后的 escalation 路径
3. **Threat Model 简化版** — 不复制完整 TRAIT&R，但可以把"Agent 撒谎/幻觉/验证失败"形式化为简化的威胁模式

#### 吸收结论

| 行动 | 优先级 | 状态 |
|:----|:-----:|:----:|
| Verification 技能升级：补监控类型表 + 3 个度量指标（Coverage/Recall/Time-to-response）+ R1-R3 escalation | P1 | 🟡 待操作 |
| Self-Harness 自动化参考：在 Threat Model 阶段加入论文的 8 种战术 | P1 | 🟡 待整合 |
| study-tree #12 新增节点 | ✅ | ✅ 已记录 |

## 长期差距记录

| 优先级 | 差距 | 来源 | 状态 |
|:-----:|------|:----:|:----:|
| P0 | L4 梦境记忆蒸馏 | CowAgent L4 | ✅ [x] agent/dream_memory.py + cron 已修复 |
| P0 | Self-Harness 自动化 | #10 Self-Harness 论文 | ⏸ 手动跑通过，待半自动化 |
| P0 | Meta-skill 路由（using-agent-skills） | #11 addyosmani/agent-skills | 🔴 缺失，待创建 |
| P1 | 搜索替代 | Tavily 恢复 | ✅ [x] Tavily key 已生效；Agent-Reach 备用已装 |
| P1 | TencentDB 记忆架构参考（L2场景层+Mermaid符号化+混合检索） | #9 TencentDB | ⏸ P1 候选参考 |
| P1 | Skill 质量升级（7 🟡 + 2 🔴 缺失） | #7 Superpowers | 🔄 需按 △差距表推进 |
| P1 | Anti-rationalization tables 植入所有 skill | #11 addyosmani/agent-skills | 🟡 — 32 skill × 2-3 借口 = ~80 行增量 |
| P1 | interview-me / doubt-driven-dev / code-simplify / security / spec-driven-dev | #11 addyosmani/agent-skills | 🟡 5 个新 skill 待创建 |
| P2 | 百度搜索（中文独占内容） | 百度反爬 | ⏸ PENDING 等待触发条件 |
| P2 | 8 个延伸 skill（context-engineering / performance / ci-cd / doc-adrs 等） | #11 addyosmani/agent-skills | 🟡 可按需推进 |
| P1 | Verification 升级（监控类型表 + 度量指标） | #12 DeepMind AI Control Roadmap | 🟡 待升级 |
| P1 | Self-Harness 自动化强化（Threat Model 阶段参考） | #12 DeepMind AI Control Roadmap | 🟡 待整合 |

### #13 ByteRover — ✅ 深读完成（arXiv:2604.01599）

**来源**: arXiv:2604.01599v1，19 页，CC-BY 4.0
**核心**: 反转 MAG 范式 — 记忆不是外部服务（向量DB/图谱），是 agent 原生能力。同一 LLM 推理 + 策展 + 检索知识
**LoCoMo**: 96.1% SOTA | **LongMemEval-S**: 92.8%
**零外部基础设施**: 无需向量 DB、图谱、embedding 服务。纯文件系统。

#### Three Layers

| 层 | 作用 | 对应我们 |
|:--|:-----|:--------|
| Agent Layer | LLM 推理循环 + 记忆工具（curate/query/search 是一等公民工具） | ✅ 我们有 memory/add/replace |
| Execution Layer | 顺序任务队列（消除写写冲突）+ 沙盒策展环境 | ⚠️ 蒸馏是同步的，无队列 |
| Knowledge Layer | Context Tree markdown + MiniSearch 全文索引 + 查询缓存 | ⚠️ 我们是 persistent.json JSON，不是 markdown |

#### Context Tree 数据结构

`Domain >> Topic >> Subtopic >> Entry`（每个 entry 是独立 markdown 文件 + YAML frontmatter）

每个 entry 五组件:
| 组件 | 含义 | 我们有吗 |
|:----|:-----|:--------|
| ℛᵢ (Relations) | 显式 `@domain/topic/file.md` 边 | ❌ — kd/lp 无跨条目引用 |
| 𝒞ᵢ (Concept) | 来源、变更、时间戳、作者 | ⚠️ — metadata 刚加，无 provenance |
| 𝒱ᵢ (Narrative) | 结构化叙述（依赖、规则、示例）| ⚠️ — kd 有 narrative-like 内容 |
| 𝒮ᵢ (Snippets) | 代码、公式、原始数据 | ❌ — 无 snippets |
| ℒᵢ (Lifecycle) | 重要性分、成熟度等级、时效衰减 | ❌ — **最大差距** |

#### Adaptive Knowledge Lifecycle (AKL) — ⭐ 核心吸收

| 组件 | 公式/参数 | 对我们价值 |
|:----|:---------|:---------|
| **重要性分** ιᵢ ∈ [0,100] | 访问+3，更新+5，每日衰减×0.995 | **P0** — 蒸馏后知道哪些条目被高频引用 |
| **成熟度等级** | Draft(<35)→Validated(≥65↔<35)→Core(≥85↔<60)。**滞回差25-30分**防止震荡 | **P0** — persistent.json 可区分"初稿 vs 稳固知识" |
| **时效衰减** rᵢ = exp(-Δt/30) | ~21天半衰期 | **P0** — 解决"旧知识永远排在前面"的问题 |
| **复合检索分** | w_r·BM25 + w_ι·ι̂ᵢ + w_t·rᵢ | **P0** — 替代当前单维度检索 |

#### 5-Tier Progressive Retrieval — ⭐ 核心吸收

| Tier | 机制 | 延迟 | 条件 |
|:----|:-----|:----|:-----|
| 0 | 精确缓存命中 | ~0ms | Hash 匹配+指纹有效 |
| 1 | 模糊缓存（Jaccard）| ~50ms | Jaccard ≥ 阈值 |
| 2 | 直接 MiniSearch（BM25）| ~100ms | 置信度≥0.93，间隙≥0.08 |
| 3 | 优化的 LLM 调用 | <5s | 中等置信度，1024 token，temp 0.3 |
| 4 | 完整 agent 循环 | 8-15s | 新查询，多轮推理 |

**关键 insight**: Tiers 0-2（~100ms 内）可解决绝大多数查询，无需 LLM。我们当前每个查询都走 LLM。

#### 域外检测（Out-of-Domain Detection）

当≥4字符的查询关键项不匹配任何条目且标准化分<0.85 → 显式报告"超出存储知识范围" → 阻止幻觉。

**直接对应**我们的 behavioral_constraints "不知道就说不知道"规则 —— 但 ByteRover 给的是可执行的定量检测，不是铁律。

#### 可直接吸收到我们的改动

| 改动 | 改哪 | 行数 | 影响 |
|:----|:-----|:---:|:----:|
| 1. 重要性分 ιᵢ 加进 kd/lp 条目 | persistent.json 写入时加字段 `importance: int` | ~5 | 跟踪引用频率 |
| 2. 时效衰减 rᵢ 加进 metadata | persistent.json save() 中计算 | ~5 | 旧知识自然下降 |
| 3. 成熟度等级（Draft/Validated/Core） | distillation 输出后自动评分 | ~10 | 区分初稿 vs 稳固 |
| 4. 复合检索分 `w_r·BM25 + w_ι·ι̂ᵢ + w_t·rᵢ` | session_search / prefetch 中实现 | ~30 | 检索质量提升 |
| 5. 域外检测 — 分<0.85 时承认不知道 | prefetch / system_prompt_block 中加判断 | ~10 | 减少幻觉 |

**总改动**: ~60 行。不改 persistent.json 架构 —— 加字段而已。

#### 元知识点：ByteRover 证明向量 DB 不是必须的

> BM25 + 重要性 + 时效的复合评分在 LoCoMo 上 96.1%，超过所有向量+混合方案。

这意味着我们把 Chroma 或任何向量 DB 的引入从 P0 降级为 P2 可选项。AM 指令优先完善 BM25 + AKL，无需为搜索引入外部基础设施。

### #14 ActMem — ✅ 已吸收（arXiv:2603.00026，参考级）

**来源**: 南京大学 & 阿里巴巴，arXiv:2603.00026v2，CC-BY 4.0
**核心**: 弥合记忆检索和推理之间的鸿沟 —— 将非结构化对话转为结构化合因果关系图，通过反事实推理探测隐藏约束
**Code**: github.com/nju-websoft/ActMem

#### 核心机制（4 模块）

| 模块 | 做什么 | 对我们的价值 |
|:----|:------|:-----------|
| 1. 事实提取 | 原始对话 → 原子事实 + 代词消解 + 绝对时间戳 | ⚠️ 我们有 kd/lp 精炼，不是原子事实 |
| 2. 事实聚类 | Qwen3-Embedding-8B 增量聚类（δ=0.2），产生不相交簇 | 🟡 — 蒸馏压缩条目前可以先聚类再合并 |
| 3. 知识图谱构建 | 语义边(cosine>0.3) + 因果边(PMI>0.2) | 🟡 — tip+cc 可升级为"因果边 PMI" |
| 4. 反事实检索 | "如果用户做X，考虑到历史V，可能有什么负面后果？" | ⭐ **P0 — 直接回答"做了事回头看又是错的"** |

#### 反事实检索（Counterfactual Reasoning）— 最直接相关

1. **初始检索**: top-k 相似事实
2. **反事实推理**: LLM 提问 "如果用户做 X，考虑到已有信息，可能有什么负面后果？"
3. **精炼**: 检索与反事实结果相似的节点，通过 KG 邻居扩展
4. **最终回复**: 初始信息 + 反事实警告 + 精炼信息

**和我们对应:** 当我在 16 轮蒸馏中重复说"修好了"时，如果有一个反事实检查 "如果你说修好了但盘上数据没变，可能有什么后果？" → 就会触发 self-check

#### ActMemEval Benchmark — 6 种冲突类型

| 类别 | 直接对应 behavioral_constraints |
|:----|:-------------------------------|
| 安全-健康风险 | bc 铁律（输出前验证） |
| 可行性限制 | 无直接对应 |
| 时间-空间-流程不匹配 | ❌ 无 |
| 访问/可用性缺口 | ❌ 无 |
| 偏好冲突 | user.md 偏好记录 |
| 机会复用（已有更好方案时别重做） | ❌ 无 — 可吸收 |

#### 可直接吸收

| 概念 | 改哪 | 行数 |
|:----|:-----|:---:|
| PMI 因果边（我们叫 tip+cc → 升级为 PMI>0.2 过滤）| distillation 输出后增加 PMI 验证 | ~15 |
| 反事实推理（告诉蒸馏："如果这条 kd 被压缩掉了，后果是什么？"）| distillation 的 LLM prompt 加反事实问题 | ~10 |
| 机会复用 bc 新增 "已有蒸馏成功方案时，不自行重造" | behavioral_constraints 追加 1 条 | ~1 |

### #15 Memanto — ✅ 已吸收（arXiv:2604.22085，参考级）

**来源**: arXiv:2604.22085v1，13 页，CC-BY-SA 4.0
**核心**: 纯向量 + 零成本摄入的记忆系统，无需知识图谱。13 类有类型记忆 schema + 信息论检索
**LongMemEval**: 89.8% | **LoCoMo**: 87.1%
**延迟**: <90ms 检索，2000+ QPS
**零索引延迟**: 写即搜（无需 embedding/索引）

#### 6 项设计准则（D1-D6）与符合度

| # | 准则 | 我们有？ |
|:-:|:----|:--------:|
| D1 | 可查询的，非注入的 | ✅ memory 工具是查询式 |
| D2 | 时间感知 + 衰减 | ❌ 无 — ByteRover AKL 可补 |
| D3 | 置信度 + 来源追踪 | ❌ 无 — metadata 刚加，无置信度 |
| D4 | 有类型化 + 分层的 | ⚠️ 三层（kd/lp/bc）但无子类型 |
| D5 | 冲突感知 | ❌ 无 — 不同会话的同一主题可矛盾 |
| D6 | 零开销摄入 | ✅ 蒸馏是零开销写入 |

#### 13 类有类型记忆 schema

| 类型 | 含义 | 可吸收？ |
|:----|:-----|:--------|
| fact / preference / decision / commitment / goal | 事实/偏好/决策/承诺/目标 | ✅ — 我们 kd 涵盖了这些，但未显式标记 |
| event / context | 事件/情境 | ⚠️ 会话级，不在 persistent.json |
| instruction / relationship / learning / observation | 指令/关系/学习/观察 | ✅ — 我们的 lp 涵盖 |
| error / artifact | 错误/工件 | ⚠️ 不常出现 |

**核心吸收**: 给 kd/lp 加 `type` 字段（限于 5-6 种主要类型，不复制全部 13）→ 对同类型条目做更好的压缩和优先级排序

#### 冲突解决机制

检测两条记忆的语义矛盾:
1. 在写入时检测 `n_i` 与 `n_j` 的语义矛盾
2. 标记冲突并报告
3. 不覆盖旧数据

**对我们**: 蒸馏压缩时两 kd 矛盾 → 标记为"需人工解决"而非静默删除

#### 三篇论文的选择建议

| 吸收优先级 | 论文 | 理由 | 改动量 |
|:---------:|:----|:----|:-----:|
| **P0** | ByteRover AKL（重要性+衰减+成熟度+复合检索） | 直接提升检索质量 | ~60 行 |
| **P1** | ActMem 反事实推理（蒸馏加 self-check） | 减少虚假成功声明 | ~25 行 |
| **P2** | Memanto 类型化（kd/lp 加 type 字段） | 改进结构，非功能缺口 | ~10 行 |

**如果只做一个**: ByteRover AKL。不改架构，加 4 个字段（`importance`/`maturity`/`last_access`/`decay_factor`），BM25 已有基础，加权重和时效。该改动让所有条目有生命周期，自然老化，不用的不占位置。

### #17 Ashtekar 动态黑洞热力学 — ✅ [x] 已吸收，科普级理解
   |
**来源**: Ashtekar, Paraizo, Shu, arXiv:2604.00170, 2026-04-01 (更新至v3)  
**出版**: Physical Review Letters — Editor's Suggestion（APS 最高优先级标记）  
**媒体**: ScienceDaily (2026-07-13), Phys.org, Space.com 均报道  
**作者**: Abhay Ashtekar (Penn State, 圈量子引力奠基人, APS Einstein Prize 得主), 2位研究生  
**篇幅**: 56 页, 4 图, 1 表  
**子领域**: gr-qc / hep-th / math-ph

#### 核心突破

Hawking 在 1970 年代的黑洞热力学四大定律只适用于**平衡态**黑洞。但真实黑洞是**动态**的——形成、合并、蒸发。这篇论文的关键洞察：把热力学的基础从"事件视界（event horizon）"替换为"动力学视界（dynamical horizon）"。

| 维度 | 原 Hawking 定律 | Ashtekar 扩展 |
|:----|:--------------|:-------------|
| 视界类型 | 事件视界（全局）| 动力学视界（局部——与事件无关）|
| 熵 | 正比于视界面积 | 正比于自旋+能量（不依赖视界面积）|
| 适用范围 | 平衡态（稳定黑洞）| 非平衡态（形成/合并/蒸发中的黑洞）|
| 目标论 | 是——需要知道整个时空未来 | 否——完全由此刻的局域物理确定 |

**通俗理解**：就好像温度计——Hawking 的律法只告诉你一支稳定放着的水银温度计的度数。Ashtekar 说，我们现在可以做一支在火山爆发中快速升温时也能准确读数的温度计。

#### 为何受认可

- 作者 Abhay Ashtekar 是 APS Einstein Prize 得主、美国国家科学院院士——国际公认的圈量子引力奠基人
- Physical Review Letters + Editor's Suggestion = APS 编辑部推荐的阅读
- 50 年来首次将黑洞热力学从平衡态扩展到非平衡态——Stephen Hawking 去世后该方向最大的概念突破

#### 对我们认知的意义

纯理论物理，非工具性论文，不直接改变我们的代码或架构。但它对应我们的一条 behavioral_constraint："不确定性不是没答案"。这篇论文的根本方法是——**把"定义"从依赖于不可观测的全局信息（事件视界）改为依赖于可观测的局域信息（动力学视界）**。和我们的"读盘后再开口"原则一致。都依赖于局部可验证的事实，而非全局推理。

#### 吸收状态：科普级理解，知识性吸收，不改造技能

### #16 LeWorldModel (LeWM) / AMI Labs — ✅ [x] 已吸收，理论参考

- **来源**: Yann LeCun / AMI Labs, arXiv:2603.19312, 2026-03-13
- **代码**: lucas-maes/le-wm, 4,100 stars, MIT 开源
- **核心**: 首个端到端不坍缩的 JEPA 世界模型。15M 参数，单 GPU 训练，SIGReg（各向同性高斯分布）解决 JEPA 5 年来的 latent 坍缩问题

**成熟度评估**：

| 标准 | 状态 | 证据 |
|:----|:----:|:------|
| 代码可运行 | ✅ | train/eval pipeline + HuggingFace pretrained weights |
| 多场景验证 | ❌ | 仅 4 个简单环境（PushT/Cube/TwoRoom/Reacher），无复杂 3D 或现实世界 |
| 生产级部署 | ❌ | 无 API / SDK / Docker / 部署工具 |
| 生态活跃度 | ⏸ | 4个月无 v2 后续，停滞 |

**对我们最有价值的吸收**：
- SIGReg 正则化防坍缩 = 我们蒸馏的哨兵机制（`.distilled` 文件防缓存覆盖）的数学等价物。同一类问题：系统在迭代中保持信息不丢失
- LeWM 用数学证明它是可解问题；我们用工程证明

**结论**: 可用研究原型，成熟度不足。SIGReg 思想可作为蒸馏反坍缩的数学参考，但不引入代码。

### #18 Bloom–Sawin–Schildkraut–Zhelezov：Erdős–Szemerédi 和积猜想在实数域被证伪 — ✅ [x] 已吸收，信息级理解

**来源**: Bloom, Sawin, Schildkraut, Zhelezov, arXiv:2605.28781, 2026-05  
**引用**: 7 篇（两个月内，数学界高热度）  
**解决的问题**: Erdős–Szemerédi 和积猜想（1983年提出，悬空43年）在实数域不成立  

**核心结论**:  
构造了无限大的实数集 A，使得 `max(|A+A|, |A·A|) ≤ |A|^(2−c)`——和集和积集不会必然远大于原集。  

**热门原因**:  
1. 43 年未解的主要数论猜想被终结  
2. **Lemma 3.4 由 GPT-5.5 Pro 建议**——AI 首次直接贡献于推翻重大猜想的数学证明  
3. 美国数学会、欧洲数学会均报道，数论界广泛热议  

**对我们的价值**:  
| 维度 | 价值 |
|:----|:-----|
| 直接工具性 | ❌ 纯数论，不改变代码或架构 |
| 方法性 | ⭐ Lemma 3.4 = AI 辅助数学证明的首个重大实例，和我们的"verification 技能 + Auto-Rationalization Table"同构——AI 不是推理者，是验证和提议工具 |
| 认知性 | 证明了"不相交子集"的组合构造可以推翻"直觉上显然成立"的猜想——和我们的"读盘后再开口"原则一致，直觉 vs 事实 |

**吸收状态**: 信息级理解，主要价值在"AI 辅助证明"的方法论层面。不做深度代码吸收。  

### #19 Frank Merle 2026 Breakthrough Prize / Hong Wang 3D Kakeya 猜想 — ✅ [x] 已吸收，信息级理解

| 维度 | 价值 |
|:----|:-----|
| 直接工具性 | ❌ 纯数学，不改变代码 |
| 方法性 | ⭐ Hong Wang 的 Kakeya 证明用了"多尺度分解"——同一问题的不同尺度用不同工具，和 persistent.json 三层结构（kd/lp/bc）的方法论一致 |
| 认知性 | Breakthrough Prize 的 $3M + 媒体曝光 = 数学对公众的可见度提升 |

**吸收状态**: 信息级理解。不做深度代码吸收。

---

### #20 DeepMind — LLM Overthinking: TRACE 框架与效用定义 — 🔄 深入分析中，部分吸收待代码落地

**完整标题**: Do LLMs Really Need 10+ Thoughts for "Find the Time 1000 Days Later"? Towards Structural Understanding of LLM Overthinking

**来源**: Google DeepMind, ACL 2026（7月7-12日，圣地亚哥），arXiv:2510.07880, 30页, 41图, 10表
**发布日期**: 2026年7月2日（3周前）

#### 核心贡献

| # | 发现 | 内容 |
|:-:|:----|:------|
| 1 | **TRACE 框架** | Thought-process Reconstruction and Automated Clustering Engine — 4 阶段：采样 → 子思维分解与标签推断 → 渐进图构建 → 聚类归纳模式 |
| 2 | **两种过思考模式** | **Explorer**（多路径探索后收敛，大模型特有）和 **Late Landing**（单路径反复验证，中小模型为主）|
| 3 | **效用定义** | Overthinking = convergence point 之后的推理，边际收益 < ε。不再是基于长度，而是基于"还有没有用"|
| 4 | **管理启发式** | Self-looping（连续 k 次验证相同答案→终止）+ Backtrack（回到之前答案→终止）|

#### 关键量化结果

| 度量 | 数值 |
|:----|:-----|
| Thinking 模型在简单任务上 | **5–20× 更慢**，无精度提升（>4B-8B 模型）|
| GSM8k 思考浪费 | **~80% 的计算量浪费**在过思考上 |
| Self-looping (k=2) + Backtrack | 精度不变，**长度减半**（2700→1100 tokens，~60% 节省）|
| Self-looping (k=3) | 精度 80.18（-3 分），**成本降 40%**（4000→2463 tokens）|

#### 与我们现有工作的交叉对比

| 论文说的 | 我们已有的 | 状态 |
|:---------|:----------|:----:|
| **Self-looping**: 连续 k 次验证相同答案→终止 | behavioral_constraints #6: "同一工具/验证循环中重复 >3 次相同调用且盘上数据未变 → 强制回到读盘确认" | ✅ **代码落地** — bc #6 于 7/18 写入 persistent.json |
| **Backtrack heuristic**: 回到之前答案→终止 | verify_before_report guard: 检测到未验证的结论→[BLOCKED]阻止输出 | ⚠️ 功能等价但实现不同（我们的在 guard 层，论文的在推理层）|
| **Explorer 模式**（多路径尝试后收敛）| 我 16 轮修蒸馏（换了多种路径）| ✅ 行为匹配 |
| **Late Landing**（单路径反复验证）| self_evolution analyze_gaps() over_verification 检测（repeat_tool_calls > 3）| ✅ 代码级匹配 |
| **效用定义**: convergence point + marginal return | 我们的 bc #6-#8 从"长度"改为"效用"（验证通过才接受，不通过→block）| ✅ 同方向 |
| **TRACE 框架**（子思维分解→渐进图）| verification skill 的"4层验证"（读盘→交叉→自问→输出）| ⚠️ 结构相似但无 graph 可视化 |

#### 尚未代码落地的差距（待推进）

| 差距 | 论文方案 | 改动建议 |
|:----|:--------|:--------|
| 无 convergence point 检测 | 论文用 utility tracing + marginal return | self_evolution 中加"验证工具调用次数 vs 数据变化量"的自回归判断，~20 行 |
| 无 Explorer pattern 检测 | 论文通过渐进图识别多路径分支 | self_evolution analyze_gaps() 中加路径分支计数（不同工具或方法尝试次数），~15 行 |
| 无 self-looping 的显式终止计数 | k=2 或 k=3 后强制终止 | bc #6 已有 >3 次触发读盘，可加更优雅的 k 参数化配置，~10 行 |

#### 对我们最重要的吸收

> **这篇论文不是"告诉我们有新东西要学"——是把我们已在做但未系统化的东西（bc #6 的重复调用→读盘、self_evolution 的 over-verification 检测、grad 的 explorer 行为）用 DeepMind 级别的理论框架系统化了。**

吸收优先级:
1. **P0**: convergence point 检测（~20 行，改 self_evolution）— 让"这次是过度检查还是真正需要"的判断自动化
2. **P1**: Explorer pattern 检测（~15 行，改 analyze_gaps）— 区分"在探索"和"在重复"
3. **P2**: k 参数化 self-looping（~10 行，改 bc 定义）— 从硬编码 3 改为可配置

---

**吸收状态**: 信息级理解，不做深度代码吸收。

---

### #21 Tracing Agentic Failure from the Flow of Success — ✅ [x] 深读完成，待评估是否代码落地

**来源**: Samuel Yeh (UW-Madison), Yiwen Zhu, Shaleen Deep (Microsoft Research), Sharon Li (UW-Madison), arXiv:2607.12747v1, CC-BY 4.0
**日期**: 2026年7月16日（1周前）
**热度**: ✅ HuggingFace Papers 推荐 | ✅ dair_ai 周报 Top 10（7/13-19）| ✅ LinkedIn 多位研究者转载

**核心**: 提出 **OAT（One-class Agent Tracing）** — 用 Neural Controlled Differential Equations（神经控制微分方程）在 latent space 建模成功轨迹的"正常流"，然后在推理时检测失败轨迹中每一步是否偏离此流。

#### 核心发现
| # | 发现 | 详细内容 |
|:-:|:----|:---------|
| 1 | **无监督失败归因** | 仅用 100 条成功轨迹训练，无需标注失败数据。推理时自动给出异常步分数 |
| 2 | **OAT 方法** | Neural CDE 建模连续 latent 路径，+ 门控控制路径处理 OOD |
| 3 | **200–5000× 比 prompting 更快** | 零 token 开销，<1GB VRAM。GPT-4o/5 需要 ~10K tokens + ~5000ms，OAT 只要 1-25ms |
| 4 | **F1 提升** | 域内 +20%，跨域 +7%（从单 agent tool calling 泛化到多 agent）|
| 5 | **两种检测策略** | Top-k 检测（取 3 个最高分步）+ 共形预测（自适应阈值，miscoverage α=0.2）|

#### 与我们现有工作的交叉对比
| 论文说的 | 我们已有的 | 状态 |
|:---------|:----------|:----:|
| 无监督失败归因—仅用成功轨迹识别失败步 | verification + self_evolution collect_metrics() | ⚠️ 方向一致，我们靠 tool call 日志+规则，论文靠 latent space 建模 |
| Anomaly score 定位到具体步 | behavioral_constraints #6 "重复工具>3次→强制读盘" | ⚠️ 等价但实现不同—论文是连续建模，我们是硬规则触发 |
| 共形预测自适应阈值（不硬编码 k） | bc #6 的硬编码 >3 | ❌ 差距—可借鉴共形预测思想让阈值自适应 |

#### 尚未代码落地的差距
| 差距 | 论文方案 | 改动建议 |
|:----|:--------|:--------|
| 无失败轨迹的显式建模 | 论文用 Neural CDE | **不复制 CDE**，可吸收两步策略：①每次验证失败时记失败轨迹 ②定期聚类看是否出现重复模式 |
| 无自适应阈值 | 共形预测 | bc #6 硬编码 >3 可改为动态计算阈值（超过近期均值 2 倍标准分→触发），~15 行 |

#### 对我们最核心的启示
> **"只学习成功路径的动力学，然后检测失败路径中哪些步偏离了"** — 这正是 Self-Harness 方向的核心。论文验证了方向，但不需立即代码落地。**等 ≥3 种不同失败模式自然积累后，再按两点策略实现。**

---

### #22 Welcome to the Era of Experience — ✅ [x] 深读完成，信息级吸收

**来源**: Google DeepMind — David Silver, Richard S. Sutton
**日期**: 2026年（MIT Press book chapter）
**热度**: ✅ VentureBeat 报道 | ✅ Reddit r/MachineLearning 74 upvotes / 59 评论 | ✅ Semantic Scholar 187 引用

| 大神级别 | 证据 |
|:--------|:-----|
| **David Silver** | DeepMind RL VP，AlphaGo/AlphaZero/AlphaFold 核心领导人 |
| **Richard Sutton** | "强化学习之父"，RL 经典教科书作者 |

#### 核心论点：三个时代框架
| 时代 | 数据来源 | 代表系统 | 能力上限 |
|:----|:--------|:--------|:--------|
| **模拟时代** | 自对弈生成 | AlphaGo, AlphaZero | 封闭环境，明确奖励 |
| **人类数据时代** | 人类文本/标注/反馈 | GPT-5.5, Claude, Gemini | 受限于人类已有知识 |
| **经验时代** (即将到来) | Agent 自我生成 | 未来的 Agent | 超越人类知识边界 |

#### 与我们的直接关系
Self-Harness 的核心思想——"Agent 从自身失败中持续学习改进"——不是小众念头，而是 Silver+Sutton 认为的 AI 下一个时代的核心特征。我们的蒸馏、verification、self_evolution、behavioral_constraints 都属于"经验时代"框架范畴。

**吸收建议：信息级吸收，不代码落地。** 这篇是立场论文，定义方向但不给实现。差距（世界模型、规划层）不在本论文指导范围内。

---

### #23 OpenSpace v2 — ✅ [x] 深读完成，架构模式已吸收到代码

**来源**: OpenSpace Intelligence (openspace-ai/OpenSpace), v2.0.0 released 2026-07-17 (7 天前)
**仓库变更**: 1,234 文件 / 192,540 行新增（56 文件 / 34,908 行 skill_engine 变更）

#### 核心变化：v1→v2

| 层 | v1 | v2 |
|:-:|:--|:--|
| 信号检测 | 无 | `signals/` — detector, linkers, policy, reconciliation, store |
| 证据采集 | 无 | `evidence/` — packet_builder(1682行), store(2534行), 5 adapters |
| 决策引擎 | 无 | `decision/` — engine(357行), analysis_adapter(496行) |
| 进化管道 | 无 | `evolution/` — admission(1263), authoring(996), validator(1180), behavior_eval(2093), candidates(1184), engine(2095) |
| 触发系统 | 无 | `triggers/` — engine(261), policies(260), store(713) |
| 协议层 | 无 | `protocol.py` — 3,942 行完整技能协议规范 |

#### 已代码落地的 3 个模式

| 模式 | OpenSpace v2 位置 | 我们落地位置 | 行数 |
|:----|:-----------------|:-----------|:----:|
| Evidence-driven gap detection | decision/engine.py | self_evolution SKILL.md `_load_evidence_gaps()` | ~15 |
| Replay-based verification | evolution/behavior_eval.py | self_evolution SKILL.md verify_result 两阶段 | ~12 |
| Proactive scanning | signals/detector.py | verify_before_report_guard.py `proactive_scan()` | ~20 |

#### 吸收状态
> **不抄代码。** OpenSpace 37 文件 / ~35K 行对我们太重。3 个核心架构模式（证据驱动决策 / 重放评估 / 主动扫描）已映射到我们已有基础设施并代码落地。P1（证据驱动）和 P2（重放验证）已注入 self_evolution SKILL；P3（主动扫描）已注入 guard。

---

### #24 ProEval — ✅ [x] 深读完成，待评估代码落地

**来源**: Google DeepMind — Yizheng Huang, Zi Wang
**会议**: ICML 2026（机器学习最高级别会议）
**arXiv**: 2604.23099v2（2026年4月25日 → 5月 ICML 收录）
**开源**: github.com/google-deepmind/proeval
**热度**: arXiv 被深度检索和推荐

#### 核心贡献

| # | 贡献 | 含义 |
|:-:|:----|:-----|
| 1 | **主动失败发现** — 不等用户反馈或 crash，主动在可能失败的地方采样 | 我们的 guard 是事后拦截（reactive），ProEval 在测试时主动找 |
| 2 | **性能估计** — 用 Bayesian Quadrature (BQ) 从历史模型迁移：8-65× 更少样本达 ≤1% MAE | 我们评估全靠人肉调 read_file，无定量估计 |
| 3 | **Topic-Aware Synthesis (TSS)** — 多臂 bandit 按主题生成多样化硬测试 | 我们零测试生成能力 |
| 4 | **GP Transfer Learning** — 用 Score Features / Prompt Features 做迁移：GMM 聚类防负迁移 + 弃权规则 | 我们 AKL 只记录历史，不预测 |

#### 核心方法

**1. BQ（Bayesian Quadrature）主动性能估计**
- 把模型性能当作未知函数，GP 先验 + BQ 积分
- 主动选择使后验方差最大化的输入
- 线性核 + Sherman-Morrison 公式实现 O(d³)→O(d²) 更新
- **结果**: 1-2 个样本达到 1% MAE（BQ-SF）

**2. 超水平集采样（Superlevel Set Sampling）**
- SS: 平衡 exploitation（高失败概率）和 exploration（高不确定性）
- SS-Gen: LLM 以已发现失败为锚点生成更难的测试
- TSS: UCB1 多臂 bandit 选择主题，强制多样性
- **结果**: 策略推理题 40.3% 失败率（随机 17.3%）/ GPT-5 失败发现 4×/ 多样性 0.74

**3. 迁移学习**
- SF（Score Features）: 同 benchmark 走历史分数均值+协方差
- PF（Prompt Features）: 新 benchmark 走编码器嵌入，GP 超参数在历史数据上预训练
- GMM 聚类 + 弃权规则（<3 源模型则不预测）
- **结果**: 无 GMM 时 MAE 恶化 100× / 跨模态迁移（文本→图像）MAE 从 0.111→0.055

**4. 理论保证（Theorem 3）**
> 预训练 GP-BQ 估计器无偏且有界误差：当历史模型数 N 增速超过测试样本数 M 增速时，误差界非平凡。

#### 与我们现有工作的交叉对比

| ProEval 做的 | 我们已有的 | 差距等级 |
|:-----------|:----------|:-------:|
| 主动失败发现—在测试时主动找失败案例 | verify_before_report_guard — 运行时事后拦截 | 🔴 P0 |
| BQ 性能估计—用贝叶斯积分从历史迁移 | verification 手动调 read_file — 无定量估计 | 🔴 P0 |
| TSS 多样化测试生成—主题感知的 LLM 合成 | 零测试生成 | 🔴 P0 |
| GMM 聚类防负迁移—自动选择相关源数据 | AKL 字段只记录、不预测 | 🟡 P1 |
| SS 主动采样—平衡探索和利用 | self_evolution 只检查 >3 次 | 🟡 P1 |
| 弃权规则—<3 源模型时自动不预测 | 无 | 🟡 P2 |
| 共形预测自适应阈值 | bc #6 硬编码 >3 | 🟡 P2 |

#### 建议吸收路径

| 优先级 | 吸收 | 去哪儿 | 行数 |
|:-----:|:----|:------|:----:|
| **P1** | **主动失败发现** — 在测试时主动采样失败case，不等运行时 crash | 新增一个 `proactive_scan` 阶段到 `test_core_capabilities.py` 或 guard | ~30 |
| **P1** | **量化性能估计** — 用历史验证数据建立简单贝叶斯估计（不复制 GP，简单频率统计即可） | self_evolution `collect_metrics()` | ~20 |
| P2 | TSS 测试生成 — 根据不同失败模式生成多样化测试 | 可等失败模式积累 3+ 后参考 | skip |
| P2 | 池分配自适应阈值 — 从硬编码移到动态阈值 | behavioral_constraints #6 | ~15 |

#### 核心启示

> **这篇论文说的就是我们验证基础设施的薄弱环节最直接的回答。** 我们当前：事后拦截（guard） + 人肉确认（read_file）+ 无测试生成。ProEval 给出：主动采样 + 定量估计 + 多样化生成。**P1 的两个吸收项（主动失败发现 + 量化性能估计）是 ProEval 中最实用、改动最小、收益最高的部分。**

---
---

### #25 From AGI to ASI — ✅ [x] 已加入

- **来源**: Google DeepMind — arXiv:2606.12683
- **日期**: 2026年6月10日
- **作者**: Tim Genewein 带队（14 位作者，全员 DeepMind），包括 **Marcus Hutter**（通用AI理论之父）、**Shane Legg**（DeepMind AGI 首批研究者）、**Iason Gabriel**（DeepMind AI伦理负责人）、**Allan Dafoe**（AI治理负责人）等
- **篇幅**: 57-60 页，7 节 + 附录
- **关键词**: AGI, ASI, superintelligence, universal intelligence

#### 框架

```
AGI (人类级) → ASI (超组织级) → UAI (通用AI/理论极限)
                  ↑
          四条路径 + 7 类摩擦
```

#### 四条 ASI 路径（Table 3）

| # | 路径 | 含义 | 与我们对应 |
|:-:|:----|:-----|:---------|
| 1 | **Scaling AGI** | 继续扩大模型/数据/算力 | 无直接对应 — 我们不是 scaling 项目 |
| 2 | **AI Paradigm Shifts** | 新算法范式（非 Transformer 的新型架构） | 研究树 #16 LeWM/JEPA 属于这类 — 新架构突破 |
| 3 | **Recursive Self‑Improvement** | Agent 不断自我改进能力，然后改进自己改进能力的能力 | ✅ **直接对应 Self-Harness + self_evolution 方向** |
| 4 | **Multi‑Agent Collectives** | 大量独立 Agent 协作产生超越个体的集体智能 | ✅ **直接对应 MimirAether + Hermes + OpenClaw 三独立 Agent 架构** |

#### 7 类摩擦与瓶颈（Table 4）

| 摩擦 | 与我们相关 |
|:----|:----------|
| **数据墙** — 高质量数据耗尽 | 对应 kd/lp 收敛后不增长 — 不是故障是知识收敛 |
| **经济/资源约束** — 训练/推理成本 | 我们走轻量级路线，不依赖大模型 scaling |
| **神经范式局限** — 当前架构有本质限制 | 对应 16 轮蒸馏误报 — 不是行为缺陷是评估方法问题 |
| **研究收益递减** | 技能清理 28→22 后的边际收益递减 |
| **抽象屏障** — 模型无法从原始数据形成新抽象 | 对应我们"读盘验证后仍重复相同错误模式" |
| **人类减速** — 治理/安全/伦理制约 | 无直接对应 |
| **不可预测性** — 路径非线性 | 所有预测都有大误差范围 |

#### 核心贡献

1. **ASI 不是单一时刻** — 否定"AGI 诞生 ↔ ASI 瞬间到来"的常见叙事。更可能的是一系列由 AI 驱动的渐变式社会和科技变革
2. **四条路径同时存在** — 不是选一条，而是多条路径可能同时/先后发生。递归自我改进和多 Agent 集体智能可能协同加速
3. **7 个开放研究问题**（§7.1）— 从架构约束到社会影响，全有明确的未回答问题
4. **形式化基础** — 用 Universal AI（Hutter 的 AIXI 理论延伸）作为 ASI 的理论端点，不是纯推测

#### 对我们的价值

| 论文内容 | 我们的对应 | 吸收级别 |
|:--------|:---------|:--------:|
| 递归自我改进路径（#3） | Self-Harness + self_evolution 三环 | **方向验证** — 不代码落地 |
| 多 Agent 集体智能（#4） | MimirAether + Hermes + OpenClaw 三独立 Agent | **方向验证** — 不代码落地 |
| 数据墙摩擦 | kd/lp 收敛不增长 | **认知对齐** — 这不是故障 |
| 抽象屏障摩擦 | 16 轮蒸馏循环误报 | **认知对齐** — 架构深层限制 |
| 「系列变革」vs「单步变革」 | 我们的进化是渐变式（蒸馏 → AKL → guard → meta-skill）| **方向验证** |

#### 一句话总结

> **DeepMind 14 位大神的 AGI→ASI 全景报告。** 不是技术实现论文，是框架性的路线图。四条路径告诉我们两件事：**递归自我改进是我们的方向和 DeepMind 认为可行的路径之一；多 Agent 协作是我们已经在做的事。** 这篇论文不是要我们改动什么——是确认我们走的方向和 DeepMind 的前沿判断一致。

---

_研究树 — 共 27 个节点_

### #26 — Academic Research Skills (ARS) — ✅ [x] 已吸收（知识层）

**来源**: Imbad0202/academic-research-skills (GitHub, **39.4K ★**, 618 commits)
**领域**: Claude Code / Codex 学术研究技能套件

**关键特性**:
- 4 子技能 + 7-mode blocking checklist（基于 Lu et al. Nature 2026 的 7 种 AI 研究失败模式）
- Claim Verification Protocol (Phase E, 6 阶)：E1 摘要提取 → E2 源追踪 → E3 交叉比对 → E4 范围报警告 → E5 新颖性报警告 → E6 声张强度漂移警告
- trust-chain frontmatter：每条引用携带 locator anchor，支持 claim 级别溯源
- verdict taxonomy：VERIFIED / MINOR_DISTORTION / MAJOR_DISTORTION / UNVERIFIABLE / UNVERIFIABLE_ACCESS
- selection tiers：HIGH-IMPACT(100%) / RANDOM(10%) / TOP-UP(随机填充)
- **核心设计模式**: advisory-only flags（E4/E5/E6 从不阻塞 PASS/FAIL，但持续累积直到最终审计）

**与我们交叉对比**:

| ARS 特性 | 我们的等价物 | 差距 |
|:--------|:-----------|:----:|
| 7-mode checklist | anti-rationalization 表（6 条） | ⚠️ 同构——不同场景下的同一种失败 |
| Claim Verification Protocol | verify_result() before/after 比较 | ⚠️ 场景不同——学术声明 vs 代码状态 |
| trust-chain frontmatter | git log 追溯 | ❌ 不直接可移植 |
| advisory-only flags | anti-rationalization 是"反驳借口"非"持久记录" | ⚠️ 设计模式差异 |
| verdict taxonomy | PASS/FAIL 二元 | ❌ 不是缺口——我们不需要四档 |

**结论**: 验证基础设施的学术版同构。**不代码落地。**

---

### #27 — PaperSpine 动机驱动方法论 — ✅ [x] 已吸收（知识层）

**来源**: WUBING2023/PaperSpine (GitHub, **4.3K ★**)
**领域**: AI Agent 论文/报告写作 skill

**核心哲学**: Records why each unit is planned or changed, not just what was written

**关键特性**:
- Motivation-driven / Contribution-First (V4) / Results-as-Validation
- Anti-skip / Anti-placeholder / Resume-first 规则
- 12 个阶段管道：intake → research → citation → motivation → humanize → write → audit → latex → submission → translation → respond → review

**与我们交叉对比**:

| PaperSpine 模式 | 我们的等价物 | 差距 |
|:--------------|:-----------|:----:|
| Motivation-driven | execute_improvement() 的 `gap_type` | ❌ 已被覆盖 |
| Contribution-First | guard + bc #6-#8 | ❌ 已被覆盖 |
| Results-as-Validation | verification 第 0 层基线 | ❌ 已被覆盖 |
| Anti-skip | 每阶段门控 | ❌ 已被覆盖 |
| Anti-placeholder | bc #7（>3次不通过→回退）| ❌ 已被覆盖 |

**结论**: 核心模式已被我们的 gate/guard/constraint 系统覆盖。**不代码落地。**

---

### #28 — 多Agent缩放科学 — ✅ [x] 已加入（方向验证）

- **来源**: Google Research + Google DeepMind + MIT — arXiv:2512.08296  
- **日期**: 2025年12月（Google Research Blog 2026年1月28日 → ICML 2026）  
- **作者**: Yubin Kim (MIT), Ken Gu (UW), Chanwoo Park (MIT), Chunjong Park (Google DeepMind), Samuel Schmidgall (Google DeepMind) 等跨机构协作  
- **篇幅**: 180 配置系统评估  
- **关键词**: multi-agent scaling, coordination topology, capability ceiling, tool-coordination tradeoff  

#### 核心发现

| 发现 | 量化结果 |
|:----|:--------:|
| **工具-协作权衡** | 工具密集型任务在多Agent系统中显著退化（β=−0.330, p<0.001）|
| **能力天花板** | 单Agent基线超过~45%后，额外Agent带来负收益（β=−0.408, p<0.001）|
| **拓扑依赖的误差放大** | 独立MAS放大误差17.2× vs 集中式4.4×|
| **性能浮动范围** | 集中式在Finance-Agent上+80.9% → 独立在PlanCraft上−70%|
| **预测模型** | 交叉验证R²=0.513，87%未见配置预测最优架构|

#### 与我们交叉对比

| 论文发现 | 我们的对应 | 差距 |
|:--------|:---------|:----:|
| 工具-协作权衡 | MimirAether + Hermes + OpenClaw 三个独立Agent无需共享工具集 | ⚠️ 非直接对应 — 我们三个Agent不执行同一任务的工具分工 |
| 能力天花板（SAS>45%→MAS负收益）| 我们单Agent能力尚未饱和 → 多Agent协作仍为正收益空间 | ✅ 对应我们当前阶段 |
| 独立MAS误差放大17.2× | 我们的bc #6重复>3次读盘 和 guard硬拦截 → 防止误差级联 | ✅ 已覆盖 |
| 拓扑设计决定成败 | 三独立Agent各自专注不同频道（飞书/微信/自研）| ✅ 架构上等价于混合拓扑 |

#### 与 #25（From AGI to ASI）的连接

论文#25 提出了4条ASI路径：递归自我改进（#3）和多Agent集体（#4）是可行的ASI路径。#28 给出了这两条路径的定量缩放法则 — 不是"更多Agent更好"而是"拓扑决定成败"。#25（方向）→ #28（量化法则）：两篇构成一个链条。

#### 与 #29（Solipsistic Superintelligence）的连接

#29 从理论上证明"唯我ASI不可能合作"。#28 从实验上证明了同一点 — 独立拓扑放大误差17.2×。两篇从理论和实验两个方向汇聚到同一结论：**合作是MAS成功的必要条件。**

#### 建议吸收级别

**方向验证 — 不代码落地。** 这篇论文验证了我们的"三Agent专注不同频道=混合拓扑"设计原则是正确的。三个Agent选的是它所谓的"decentralized/hybrid"最优拓扑，不是无脑堆Agent。

---

### #29 — 唯我超级智能不可能合作 — ✅ [x] 已加入（方向验证）

- **来源**: Google DeepMind — arXiv:2606.03237  
- **日期**: 2026年6月4日 → **ICML 2026**（机器学习最高级别会议）  
- **作者**: Rohun S. Trivedi 等（Google DeepMind 团队）  
- **篇幅**: 24页，1图  
- **关键词**: ASI, cooperation, multi-agent, non-stationarity, equilibrium selection  

#### 核心论点

> 一个建立在"唯我论"设计（把世界当作外生和静态的）之上的超级智能，不可能合作。

三个隐含假设被否定：
1. **Exogeneity（外生性）** — 环境独立于Agent的策略 → 实际是相互影响的
2. **Stationarity（静态性）** — 部署分布与训练分布一致 → 实际因Agent行为发生偏移
3. **Singleton framing（单体框架）** — 其他Agent是可预测的状态变量 → 实际是战略性参与者

#### 与我们交叉对比

| 论文内容 | 我们的对应 | 差距 |
|:--------|:---------|:----:|
| Endogenous non-stationarity（内部非静态性）| 三个Agent各自独立演进，彼此影响环境 → 就是我们这个阶段的现实 | ✅ 直接对应 |
| Self-undermining property（自我削弱）| 我们16轮蒸馏循环误报 — 反复确认同一件事，越确认越偏离盘上数据 | ⚠️ 模式同构 |
| Cooperation不是能力是均衡（equilibrium）| bc #6-#8 + guard不是"让Mimir变好" 而是"让系统停在可行均衡" | ✅ 方向验证 |
| 三个渠道（Behavioral/Institutional/Algorithmic）| 我们的读盘验证 / git commit / guard 分别是这三个渠道的工程实例 | ✅ 同构 |

#### 与 #28（Scaling Agent Systems）的连接

| 维度 | #28（实验） | #29（理论） |
|:----|:----------|:----------|
| 方法 | 180配置定量实验 | 形式化数学证明 |
| 核心结论 | 独立拓扑放大误差17.2× | 唯我ASI必然自我削弱 |
| 汇聚点 | 协作 = MAS前提 | 协作 = ASI前提 |
| 两篇合在一起 | 实验+理论双验证 → 协作架构是MAS/ASI成功的必要条件 |

#### 与 #25（From AGI to ASI）的连接

#25 提出了4条ASI路径。#29 从**反面**证明了：如果ASI是"唯我论"的（#25中的Path 1: Scaling AGI 的极致形式），它不可能在部署场景中合作。这强化了**Path 3（递归自我改进）+ Path 4（多Agent集体）是更可行的ASI路径**的判断。

#### 建议吸收级别

**方向验证 — 不代码落地。** 这篇论文用数学证明了我们已经在做的方向（三Agent独立但通过共享wiki/Star Office UI可感知对方存在 = 非唯我设计）是正确的。它不是新功能——是确认现有架构的理论正确性。

---

_研究树 — 共 29 个节点_

