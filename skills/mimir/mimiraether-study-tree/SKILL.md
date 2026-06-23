# mimiraether-study-tree

MimirAether 知识研究树——对外部技术的调研、对比、吸收结论。

## 使用方式

每次研究一个新项目后，在此记录研究结论，并标记状态 `[x]`。
研究成果树是"已消化、已决策"的知识，不是 backlog 执行清单。

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
  | L4 梦境记忆蒸馏 | **每天23:55定时**：读所有记忆→去重→蒸馏→写日记→≤50条 | **完全没有** | **最大差距 P0** |
  | L5 源码自更新 | cow self-restart + 自检 + 接力进程 | systemd 自启(可崩溃恢复) | 持平 |
- **核心待解决**: L4 梦境记忆蒸馏（定时回顾+精炼）

### #3 Agent-Reach — 🛸 已安装，正式替代 Tavily [x]
- **来源**: Panniantong，38,139 stars，本周8,108⭐（发布时间：~2026-06-10）
- **功能**: 13 平台零 API 费搜索/阅读（Twitter/Reddit/YouTube/GitHub/B站/小红书/网页/RSS/语义搜索）
- **安装**: `~/.agent-reach-venv/` via python3.12 venv，6/13 渠道激活
- **核心工具**:
  - **语义搜索** → `mcporter call 'exa.web_search_exa(query: "...", numResults: 5)'`（免费无 Key）
  - **网页阅读** → `curl https://r.jina.ai/URL`（Jina Reader，免费无 Key）
  - **YouTube 字幕** → `yt-dlp`（已安装）
  - **GitHub 搜索** → `gh search`（已认证）
  - **RSS 阅读** → 零配置
- **结论**: **正式替代 Tavily**。Tavily 当前已 401 不可用，Agent-Reach 零 API key、零配置覆盖并超越它。Tavily 的 API key 留在 OpenClaw .env 不动（安全备份），Mimir 直接用 Agent-Reach。
- **Skill**: 已安装在 `~/.openclaw/skills/agent-reach/`（search/dev/web/video/social/career 六大分类）

### #4 Codebase-Memory-MCP — ✅ 跳过
- **来源**: DeusData，12,034 stars
- **功能**: 使用 MCP 协议的代码知识图谱持久化
- **结论**: OC-04 审计决定保持现状。**跳过**。

## 长期差距记录

| 优先级 | 差距 | 来源 | 状态 |
|:-----:|------|:----:|:----:|
| P0 | L4 梦境记忆蒸馏 | CowAgent L4 | ✅ [x] agent/dream_memory.py 已上线 |
| P1 | 搜索替代 | Tavily 401 | [~] Agent-Reach候选 |
