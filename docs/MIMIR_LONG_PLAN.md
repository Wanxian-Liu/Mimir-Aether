# MimirAether 长期计划（理清 → 伙伴 → 企业级）

| 字段 | 值 |
|------|-----|
| **状态** | 活文档；战略对话维护，执行以 [`MIMIR_EXEC_BACKLOG.md`](./MIMIR_EXEC_BACKLOG.md) 为准 |
| **投入模型** | 按**任务 / token**（S/M/L），不设每周工时 |
| **伙伴期** | 无单一专项；与负责人**一起成长**，能力面达标即可 |
| **终点取向** | **企业级**自托管智能体：单主体、可审计进化、HTML 记忆真源、可 CI 验证 |

**依据**：[`MIMIR_CLARIFY_BASELINE.md`](./MIMIR_CLARIFY_BASELINE.md)、[`MIMIR_HTML_MEMORY_CONTRACT.md`](./MIMIR_HTML_MEMORY_CONTRACT.md)、[`MIMIR_OPENCLAW_BOUNDARY.md`](./MIMIR_OPENCLAW_BOUNDARY.md)、[`MIMIR_MIMICORE_SPRING_SCOPE.md`](./MIMIR_MIMICORE_SPRING_SCOPE.md)、[`DEVELOPMENT_NORTH_STAR.md`](./DEVELOPMENT_NORTH_STAR.md)。

---

## 1. 阶段（产品，非仅工程表）

| 阶段 | 目标 | 完成判据（负责人可勾选） |
|------|------|--------------------------|
| **理清期**（当前） | 身份、路径、记忆格式、泉/主脑边界钉死 | 理清 8 项对照表可一句话说清；无双通道/双记忆根一周；BACKLOG 可无人领 S 条 |
| **伙伴期** | 一起 growth，无固定「只做 X」 | 伙伴准入清单（§4）满足；ISSUES open 可控 |
| **企业级加固** | 部署、安全、观测、升级路径 | 安装文档 + 非 loopback 有 API key + 分支/CI 习惯 |
| **远景** | 独立模型机会 | 不挡前三阶段；数据与进化日志先行 |

---

## 2. 五条轨道

| 轨道 | 内容 | 真源文档 |
|------|------|----------|
| **存在方式** | 单 MA、单 gateway、`~/src/MimirAether` + `$MIMIR_AETHER_HOME` | path-contract, OPENCLAW_BOUNDARY |
| **记忆 HTML** | `memory/capsules`、`memory/wiki`、Obsidian 同根 | HTML_MEMORY_CONTRACT |
| **mimicore 泉** | 胶囊 + evolve；归档第二套 gateway/cli/agent | MIMICORE_SPRING_SCOPE |
| **Parity + 进化** | 学 Hermes 核心；tier0 + M6；非黑盒 | NORTH_STAR, M6_EVOLUTION |
| **技能与学习** | SKILL 插件化吸收；不整仓融合 | agent-skills-inventory, BACKLOG |

---

## 3. 里程碑（3 个）

### M1 — 记忆统一（理清期主干）

- 胶囊 HTML 发布与扫描（**T06 已完成**）
- wiki / Obsidian 配置指向 `memory/wiki`
- 历史 `{repo}/mimicore/public/*.md` 导入 chore（可选批次）
- `memory/index.html` 入口（可自动生成）

### M2 — 泉瘦身（理清期末 / 伙伴期初）

- 子模块内 gateway/cli/mini_agent **不进入** MA 运行时文档
- evolve + capsule_generator **保留在泉**
- 数据根 `mimicore/` 与 repo 子模块**双轨**（发布只认 data 根）

### M3 — 伙伴就绪

- 飞书/通道稳定；BACKLOG 可离线推进 S 条 + CI 绿
- 问题记入 ISSUES，不无限重试
- 进化可审计；负责人回电脑审 PR/勾选项

---

## 4. 伙伴期准入清单（成长向）

- [ ] 能回答：MA 是什么、数据在哪、记忆什么格式、与 OpenClaw/Hermes/mimicore 各什么关系
- [ ] `$MIMIR_AETHER_HOME/memory/capsules/` 有 HTML 真源；`list_capsules` 可信
- [ ] 一周：单 gateway、飞书单应用、无旧路径误启
- [ ] `MIMIR_EXEC_BACKLOG` 至少连续 5 条 S/M 完成且 tier0/CI 可证
- [ ] `MIMIR_ISSUES` open 项 ≤ 负责人约定上限（默认 5）
- [ ] 愿意把**专项任务**交给 MA（不等于 24/7；按任务/token）

---

## 5. 无人值守执行约定

| 规则 | 说明 |
|------|------|
| **清单真源** | [`MIMIR_EXEC_BACKLOG.md`](./MIMIR_EXEC_BACKLOG.md)（做）、[`MIMIR_ISSUES.md`](./MIMIR_ISSUES.md)（卡） |
| **一次一条** | 飞书：「按 BACKLOG 做下一条未勾选项」 |
| **分支** | 仅 `feat/mimir-*`；不直接推 main |
| **验证** | 每条结束：能跑则 `./run_ralph_tier0.sh`；推分支后 GitHub **Ralph** workflow |
| **合并** | 默认等负责人回电脑 |
| **卡住** | 写 ISSUES + 停；同一问题不试超过 2 轮 |
| **战略对话** | 飞书联系不到 Cursor 战略 agent；回报贴 BACKLOG/ISSUES 或 git |

---

## 6. 企业级出口（可操作）

- **部署**：`MIMIR_AETHER_HOME` + `MIMIR_ACTIVATE` / `OPERATIONS_GATEWAY`
- **安全**：密钥仅 `.env`；生产 API key；skills install 策略见 SECURITY
- **可观测**：`logs/gateway.log`、`/health`、M6 进化行
- **可演进**：Parity 契约 + 技能扩展；OpenClaw/weavevault **零部署**（仅借鉴）

---

## 7. 专业默认（负责人已认可）

| 决策 | 选择 |
|------|------|
| mimicore 部署 | **双轨**：代码在 git 子模块；发布在 data 根 `memory/capsules` + 可选同步 `~/mimiraether/mimicore` |
| Obsidian | 与 wiki 同根；canonical 仅 HTML；MD 仅在 `_drafts/` |
| memory/mimicore-runtime | 暂不建；进化审计用 M6 |

---

## 8. 修订记录

| 日期 | 变更 |
|------|------|
| 2026-05-16 | 初版：理清/伙伴/企业级五轨道 + M1–M3 + 无人值守约定 |
