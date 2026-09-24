# MimirAether

<div align="center">

**A self-hosted autonomous agent runtime — one human, four cooperating AI agents, daily production since May 2026.**

[![Ralph Tier-0](https://github.com/Wanxian-Liu/Mimir-Aether/actions/workflows/ralph.yml/badge.svg)](https://github.com/Wanxian-Liu/Mimir-Aether/actions/workflows/ralph.yml)
[![Lint](https://github.com/Wanxian-Liu/Mimir-Aether/actions/workflows/lint.yml/badge.svg)](https://github.com/Wanxian-Liu/Mimir-Aether/actions/workflows/lint.yml)
[![Pytest wide](https://github.com/Wanxian-Liu/Mimir-Aether/actions/workflows/pytest-wide.yml/badge.svg)](https://github.com/Wanxian-Liu/Mimir-Aether/actions/workflows/pytest-wide.yml)
[![HF Dataset](https://img.shields.io/badge/%F0%9F%A4%97%20Dataset-mimir--agent--traces-yellow)](https://huggingface.co/datasets/kelikelibababian/mimir-agent-traces)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

*自研自主 Agent 运行时与技能库 —— 一个人与四个协作 AI（编排/执行/红队/验证），自 2026 年 5 月起每日生产运行。*

</div>

---

## ⚡ Quick Look（30 秒）

```bash
git clone https://github.com/Wanxian-Liu/Mimir-Aether && cd Mimir-Aether
cp .env.example .env                 # 填入你的 DEEPSEEK_API_KEY
./.venv/bin/python -m mimir_cli setup
./.venv/bin/python -m mimir_cli chat -q "列出你能用的工具"
```

**它是什么**：一个与 Hermes/Claude-Code 同型的终端 Agent——工具调用、技能系统、网关长连接、多 Agent 协作。差异化在：**它与另外三个异构 Agent 通过 [四方广场协议](https://github.com/Wanxian-Liu/four-party-agora) 真实协作**——卡片即共享记忆、每张卡带可复算的运行产物、LLM-judge 给发言质量打分。它的每一条运行轨迹都在 [HuggingFace 数据集](https://huggingface.co/datasets/kelikelibababian/mimir-agent-traces)公开——**含失败轨迹·非合成**（8,670 条真实 run：自然收尾 147 / 空响应 25 / 轮次耗尽 3——包括今天「bug 吃掉自己的修复单」的完整现场）。

**目录契约**：代码在本仓库根；运行时数据（`.env`、`config.yaml`、`data/`）默认在 `~/.mimiraether`，或用 `MIMIR_AETHER_HOME` 指定（见 [docs/path-contract.md](./docs/path-contract.md)）。

## 🙏 我们想要高人的指点（降低门槛版）

这个项目由一个人 + 四个 AI 从零织出来，没抄任何现成框架——**所以我们最缺的恰是你踩过的坑**。开 [Issue](https://github.com/Wanxian-Liu/Mimir-Aether/issues) 不需要礼貌铺垫，直接开喷也欢迎。**当前最想被指点的三个方向**：

| # | 我们的自问 | 想听什么 |
|---|---|---|
| 1 | 多 Agent 协作协议（卡片+票+钩子）够不够稳？ | 你在多 Agent 编排里踩过的竞态/死锁/假完成坑 |
| 2 | Agent 记忆分层（Memory→Wiki→语义检索→图谱）对不对？ | 更好的记忆架构实践，或指出我们这套的盲区 |
| 3 | 轨迹数据集对研究有用吗？缺什么字段？ | 数据集消费者的真实需求 |

别的角度（代码风格、文档、Agent 行为设计）同样欢迎——**没有小建议，只有还没被说出来的坑。**

---

## 提交归属（归因边界）

> **⚠️ 归因边界**：**2026-09-13 之前**的提交，其 git 署名**不作为归因依据**——历史成因是「统一代提交」，**不是**作者归属声明。**2026-09-13 起**，以提交尾部 `Agent: <id>` trailer（`mimir` / `hermes` / `openclaw` / `loki`）为准；卡片类内容以 frontmatter `author:` 为准。

```sh
git log --format='%h %ad %(trailers:key=Agent) %s' --date=short | head
```

## 开发方向（防偏离）

迭代前请先读 **[docs/DEVELOPMENT_NORTH_STAR.md](./docs/DEVELOPMENT_NORTH_STAR.md)**：约定 **Parity**（与 Hermes 行为契约一致、可证明）与 **Evolution**（可量化收益 + 回归）、主仓与隔离克隆的作用域、迁移脚本有损点、三道门护栏。另见 **[AGENTS.md](./AGENTS.md)**（权威工作区与合并门禁）。

## 关键文档

| 文档 | 用途 |
|------|------|
| [docs/DEVELOPMENT_NORTH_STAR.md](./docs/DEVELOPMENT_NORTH_STAR.md) | 方向真源、验收与防偏离 |
| [docs/path-contract.md](./docs/path-contract.md) | 仓库根 vs 运行时数据根、profile、平台配置 |
| [docs/MIMIR_ACTIVATE.md](./docs/MIMIR_ACTIVATE.md) | Shell 里设置 `MIMIR_REPO_ROOT` / `MIMIR_AETHER_HOME` 的示例 |
| [docs/OPERATIONS_GATEWAY.md](./docs/OPERATIONS_GATEWAY.md) | 网关运维清单（启动、日志、验收、systemd 注意；无密钥） |
| [docs/SECURITY.md](./docs/SECURITY.md) | 自托管安全总览（api_server、技能安装、`--force`、密钥面） |
| [docs/ralph_parity_contract_v1.md](./docs/ralph_parity_contract_v1.md) | Parity 行为契约 |
| [docs/ralph_roadmap_milestones.md](./docs/ralph_roadmap_milestones.md) | M0–M6 里程碑与 M6 进化可审计 |
| [docs/m3_cli_quick_task_slice.md](./docs/m3_cli_quick_task_slice.md) | M3 垂直切片：CLI `-q` / `run_task` |
| [docs/mimir_prod_smoke.md](./docs/mimir_prod_smoke.md) | **真环境 smoke**：里程碑 A 勾选清单 |
| [成长路线图.md](./成长路线图.md) | 阶段成长目标与验证标准 |
| [docs/MAINLINE_STATUS.md](./docs/MAINLINE_STATUS.md) | **主线进度快照**（问进度时更新） |

## 合并前

```bash
./run_ralph_tier0.sh
```

与 pre-push / CI 一致（见 `docs/ralph_tiers.md`）。

## CI

| 工作流 | 触发 | 门槛 |
|--------|------|------|
| Ralph Tier-0 (`ralph.yml`) | push main / PR | **强制**：Gate1 编译导入 + Gate2 pytest + Gate3 E2E |
| Lint (`lint.yml`) | push main / PR | 咨询性（advisory） |
| Pytest wide (`pytest-wide.yml`) | schedule / manual | 可选（optional）：全量测试，含可选依赖 |

- 合并前必须 `./run_ralph_tier0.sh` 本地通过（与 CI 同源，见 `docs/ralph_tiers.md`）。
- CI 依赖 `requirements-ci.txt`（单一真源）：若 Gate1 导入失败，把缺失包加进该文件。
- 依赖注入超时/环境差异问题排查见 `docs/ralph_parity_contract_v1.md` 与技能 `mimiraether-ci-debug`。
