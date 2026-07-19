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

### #12 DeepMind AI Control Roadmap — ✅ [x] 已吸收

- **来源**: Google DeepMind, arXiv:2607.13087, 2026-06-18
- **核心**: 假设 AI 可能不可靠，在其周围加系统级防御和控制层
- **核心发现**: 分析 100 万条 agent 轨迹后，大部分异常来自 **agent 误解或过度积极不是恶意**
- **三层框架**: Individual Agent → Multi-Agent → Ecosystem
- **6 种检测类型**: CoT monitoring / Action monitoring / Honeypots / PR monitoring / Activation monitoring / UEBA

**与我们映射:**
| DeepMind 层 | 我们有的 | 差距 |
|:-----------|:--------|:----:|
| CoT monitoring | verification 技能 — 读盘验证 | 读盘是事后检查，不是执行中监控 |
| Action monitoring | tool-triggers §8 自检 | 只有入口自检，无执行中追踪 |
| 度量指标 | 无 | **缺 3 个度量**：Coverage（覆盖多少失败）、Recall（检出率）、Time-to-response（发现到修复的延迟）|
| Threat Model → Mitigation | 手动 16 轮调试 | 无自动化闭环 |

**吸收行动:**
- ✅ verification 升级：补 6 种检测类型描述 + 3 个度量指标（Coverage/Recall/Time-to-response）+ R1-R3 升级路径
- ✅ behavioral_constraints 追加：同一工具/验证循环中重复 >3 次相同调用 → 强制回到读盘确认
- ⏸ Self-Harness 参考：Threat Model 阶段纳入自动化闭环方案

### #13 杨立昆 AMI Labs 系列论文 — 📥 已拉取（2026-07-19）

**来源**: Yann LeCun — 2025年底离开Meta，巴黎创立AMI Labs（$1.03B seed, NVIDIA/Samsung/Bezos投资）

#### 近两月核心论文

| 论文 | 日期 | arXiv ID | 核心内容 | 对我们价值 |
|:----|:----|:--------|:---------|:---------|
| **LeWorldModel (LeWM)** | 2026-03-13 | 2603.19312 | 首个端到端JEPA：像素→潜在空间→物理规划。15M参数，单GPU数小时。规划比基础模型快48倍 | 高 — "各向同性高斯分布防止坍缩"的方法与蒸馏防止缓存覆盖的结构对照 |
| **When Does LeJEPA Learn a World Model?** | 2026-05-25 | 2605.26379 | 首次从数学上证明JEPA何时能学到真实世界结构的条件（iff定理）| 高 — 形式化方法可借鉴到蒸馏质量评估 |
| **AI Must Embrace SAI** | 2026-02 | 2602.23643 | 反AGI论文："通用"是错误目标，应追求超人类可适应智能 | 哲学参考 |
| **Value-guided JEPA planning** | 2026-01 | 2601.00844 | JEPA做价值引导行动规划 | 中等 |

#### LeWM 结构（已拉全文）

```
Encoder: z_t = enc(o_t) — ViT tiny (~5M params)
Predictor: \hat{z}_{t+1} = pred(z_t, a_t) — Transformer (~10M params)
  ↓
ℒ_LeWM = ℒ_pred + λ SIGReg(Z)  ← 只有两个loss项（从6个超参降到1个）
  ↓
Planning: MPC + CEM in latent space (0.98s vs 47s = 48× faster)
```

**核心机制 SIGReg**: 用Cramér-Wold定理强制潜在嵌入符合各向同性高斯分布 → 防止JEPA表示坍缩。对标到我们的蒸馏：防缓存覆盖也需要"锁定正确状态"的机制（哨兵文件与之同构）

#### 吸收评估

| 维度 | 评估 |
|:----|:-----|
| 直接有用 | 中 — 非memory/蒸馏系统直接借鉴，但LeWM的"简单loss防坍缩"哲学可参考到蒸馏质量设计 |
| 研究价值 | 高 — JEPA是LLM的主要替代路线之一，理解它对研究树生态位置判断有帮助 |
| 代码价值 | 低 — PyTorch + 16×A100，不在我们当前可运行范围 |
| 平台参考价值 | 中 — AMI Labs论文发布在arXiv + GitHub开源，验证arXiv是论文主要入口 |

**结论**: 有价值但非立即吸收。标记为"可扩展知识"放在研究树中，不排行动计划。

## 论文获取平台一览

以下是世界最权威的AI/物理/数学/量子计算论文平台及其结构，供未来按兴趣查阅：

### ① arXiv.org（全球首选预印本库，⭐⭐⭐⭐⭐）

| 大类 | 子类ID | 覆盖内容 |
|:----|:------|:--------|
| **cs** — 计算机科学 | cs.AI | 人工智能（专家系统/知识表示/规划/推理 — 不含ML/CV/NLP）|
| | cs.LG | **机器学习**（深度学习/强化学习/统计学习 — 最大子域）|
| | cs.CL | 自然语言处理/计算语言学 |
| | cs.CV | 计算机视觉/模式识别 |
| | cs.RO | 机器人学（控制/感知/规划/HRI）|
| | cs.IR | 信息检索（搜索/推荐/RAG）|
| | cs.MA | 多智能体系统 |
| | cs.SE | 软件工程 |
| | cs.CR | 密码学/安全 |
| | cs.AR | 硬件架构（加速芯片/AI芯片）|
| **stat** — 统计学 | stat.ML | 统计机器学习（cs.LG论文也常投这里）|
| **math** — 数学 | math.NA | 数值分析（科学计算/优化）|
| | math.OC | 优化与控制（凸优化/非线性规划/最优控制）|
| | math.DS | 动力系统（混沌/遍历理论/非线性动力学）|
| | math.PR | 概率论（随机过程/随机矩阵/大偏差）|
| | math.ST | 统计理论/数理统计 |
| | math.GT | 博弈论（机制设计/拍卖理论）|
| **physics** — 物理 | physics.comp-ph | 计算物理（蒙特卡洛/分子动力学/格点QCD）|
| | physics.class-ph | 经典物理/电磁学/引力 |
| | physics.optics | 光学/光子学 |
| | physics.flu-dyn | 流体动力学 |
| | quant-ph | 量子物理（量子计算/量子信息/量子纠缠 — **你的兴趣**）|
| | astro-ph | 天体物理/宇宙学 |
| | cond-mat | 凝聚态物理/材料科学（含量子材料）|
| | hep-th | 高能物理—理论（弦论/QFT/量子引力）|
| **q-bio** — 生物 | q-bio.NC | 神经科学/计算神经 |
| | q-bio.QM | 定量方法（生物信息/基因组学）|
| **eess** — 电子工程 | eess.SP | 信号处理（语音/音频/视频）|

**最佳入口：** 每天新论文 → arxiv.org/list/cs.AI/new 或 arxiv.org/list/cs.LG/new  
**精确搜索：** arxiv.org/search/?searchtype=all&query=关键词  
**按时间+热度排序：** alphaxiv.org（带社区讨论）  
**PDF直链：** arxiv.org/pdf/ID

### ② Google DeepMind Publications（DeepMind 官方，⭐⭐⭐⭐⭐）

| 研究领域 | 涵盖 | 与我们关系 |
|:--------|:-----|:---------|
| **AI Safety & Control** | AI Control Roadmap, Honeypot eval, Multi-agent safety | ⭐ 已吸收 #12 |
| **Foundation Models** | Gemini Ultra 2, Veo 3, Gemma 4 | 关注，非直接吸收 |
| **World Models** | Genie 3, SIMA 2 | ⭐ 重叠 #13 LeCun |
| **Science** | 生物（AlphaFold/ALS老化/肝脏疾病）、气象（WeatherNext）、化学（分子发现）| 🟡 扩展视野 |
| **Robotics** | Gemini Robotics、物理Agent | 🟡 兴趣 |
| **Multi-agent** | Co-Scientist、协作推理 | ⭐ 与Self-Harness相关 |

**入口：** deepmind.google/research/publications — 按年份/作者/领域筛选

### ③ OpenReview.net（同行评审会议论文，⭐⭐⭐⭐）

| 会议 | 领域 | 特点 |
|:----|:----|:----|
| **ICLR** | 表示学习/深度学习 | 论坛式公开审稿，审稿人+作者讨论可见 |
| **NeurIPS** | 神经信息处理系统 | AI/ML最大会议（~10K论文/年）|
| **ICML** | 机器学习 | 纯ML，理论+应用 |
| **AISTATS** | 统计学习/AI | 更偏理论/统计 |
| **COLT** | 学习理论 | 纯理论（PAC/泛化界/在线学习）|

**入口：** openreview.net — 按会议/年份/领域浏览 + 带作者回复

### 兴趣领域论文星级地图

| 你的兴趣 | 最佳第一站 | 最佳第二站 | 最活跃时间 |
|:--------|:---------|:---------|:---------|
| 🧠 **AI / 机器学习** | arXiv cs.LG | DeepMind Publications | 全年（5-6月/12月最多）|
| 🔬 **物理** | arXiv physics.*（quant-ph, comp-ph, flu-dyn等特定子域）| DeepMind Science | 全年 |
| 📐 **数学** | arXiv math.*（NA/OC/DS/PR）| — | 全年 |
| ⚛️ **量子计算** | arXiv quant-ph | — | 全年 |
| 🔗 **交叉领域**（科学+AI）| DeepMind Publications Science | arXiv cs.CE | 2025-2026井喷 |

## 使用习惯（备忘）

- **每天刷arXiv** → 只看 cs.LG + cs.AI + quant-ph 的新论文（每日列表 ~100-300篇，扫标题 3分钟）
- **深读** → PDF直链 `arxiv.org/pdf/ID`
- **话题跟踪** → `web_search "Yann LeCun 2026 site:arxiv.org"` 或 `web_search "DeepMind + [兴趣关键词] 2026"`
- **价值判断标准**：能否直接吸收到我们（memory/dream distillation/verification/self_evolution/self-harness）系统中。与这些组件无直接映射→标记PENDING或跳过

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
|| P2 | 8 个延伸 skill（context-engineering / performance / ci-cd / doc-adrs 等） | #11 addyosmani/agent-skills | 🟡 可按需推进 |
| P1 | SkillOpt skill 优化器参考 | #14 SkillOpt | ⏸ 待代码化 — 需研究能否接入 self_evolution 作为优化器 |
| P1 | Kairos 后悔感知蒸馏度量参考 | #15 Kairos | ⏸ 待引入蒸馏质量评估 — 需研究"后悔"指标的蒸馏效用函数 |

### #14 SkillOpt（Microsoft Research）— ✅ [x] 已吸收
- **来源**: arXiv:2605.23904, Microsoft Research / 4 位中科学者, 2026-05-22
- **核心**: Skill 优化的独立 optimizer 模型 — 把评分过的 rollout 转为 bounded add/delete/replace 编辑，**只有严格提高验证分数时接受修改**
- **关键机制**:
  | 机制 | 解决什么问题 | 与我们关系 |
  |:----|:-----------|:---------|
  | **文本学习率预算** | 防止单次改动过大，类似梯度下降的步长裁剪 | ✅ 我们的 self_evolution 缺"每次改多少"的控制 |
  | **拒绝编辑缓冲区** | 不接受验证分数没提高的修改 | ✅ 我们 16 轮蒸馏失败正是"没验证就用了新代码" |
  | **epoch-wise 慢速/元更新** | 运行时从 1-3 轮编辑开始，逐步增加至 10-20 轮 | ✅ 我们的自进化缺少渐进式规模控制 |
- **结果**: 6 benchmark, 7 目标模型, 3 execution harness — **全部 52 个测试单元格最佳或并列最佳**
- **GPT-5.5 量化提升**: 无 skill → +23.5（直接对话）/ +24.8（Codex）/ +19.1（Claude Code）
- **吸收建议**:
  1. 把 SkillOpt 的"拒绝编辑缓冲区"模式融入 self_evolution 的 decision_ring — 验证分数没提高就不接受修改
  2. 文本学习率预算控制每次自进化时产生的改动规模（当前是一次性改整段代码）
  3. 等 self_evolution 积累 ≥3 轮测试数据后，再考虑引入独立的 optimizer 层

### #15 Kairos（Regret-Aware World Model）— ✅ [x] 已吸收
- **来源**: arXiv:2606.16533, 百人团队, 2026-06-15 / 2026-07-03 更新
- **核心**: 「后悔感知」原生世界-行动模型，不模拟所有像素，只维持对具身控制最重要的信息
- **三阶段学习框架**:
  | 阶段 | 内容 | 与我们关系 |
  |:----|:-----|:---------|
  | **Learn** | 跨具身数据课程（多本体/多任务协调） | 🟡 persistent.json 的多源整合可参考 |
  | **Maintain** | 混合线性时间注意力（长序列高效在线更新）| ✅ `\_maybe\_compact` 的增量压缩可借鉴 |
  | **Deploy** | 感知延迟/内存/硬件约束的实际部署 | 🟡 我们蒸馏的部署环境（gateway/terminal）约束类似 |
- **后悔感知**: 不仅预测未来，还要知道它**过去错在哪**— 最相关的概念
- **五个维护维度**: 对象状态、空间关系、接触条件、任务进度、动作后果、失败边界、部署不确定性
- **吸收建议**:
  1. **后悔感知度量**融入蒸馏质量评估 — 当前我们只记"成功了/没成功"，不记"这次错在哪"
  2. 三阶段课程思路可借鉴给 persistent.json 的层次化维护（原始记录 → 场景层 → 结构化蒸馏）
  3. 混合线性时间注意力可作为 long-term recall 的可选参考架构

## 论文获取平台一览

详见上文 `​### ① arXiv` / `### ② DeepMind Publications` / `### ③ OpenReview.net` 三节 + `兴趣领域论文星级地图`

## 论文更新日志

| 日期 | 操作 | 内容 |
|:----|:----|:-----|
| 2026-07-18 | 新增 #14 | SkillOpt — Microsoft Research skill 优化器（arXiv:2605.23904）|
| 2026-07-18 | 新增 #15 | Kairos — 后悔感知世界模型（arXiv:2606.16533）|

