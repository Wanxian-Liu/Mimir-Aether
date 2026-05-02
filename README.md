# MimirAether

自主 Agent 运行时与技能库：**主开发树**默认位于 `~/.openclaw/projects/MimirAether`（见 `docs/path-contract.md`）。

## 开发方向（防偏离）

迭代前请先读 **[docs/DEVELOPMENT_NORTH_STAR.md](./docs/DEVELOPMENT_NORTH_STAR.md)**：约定 **Parity**（与 Hermes 行为契约一致、可证明）与 **Evolution**（可量化收益 + 回归）、主仓与隔离克隆的作用域、迁移脚本有损点、三道门护栏。另见 **[AGENTS.md](./AGENTS.md)**（权威工作区与合并门禁）。

## 关键文档

| 文档 | 用途 |
|------|------|
| [docs/DEVELOPMENT_NORTH_STAR.md](./docs/DEVELOPMENT_NORTH_STAR.md) | 方向真源、验收与防偏离 |
| [docs/path-contract.md](./docs/path-contract.md) | Agent home / profile / 平台配置三层路径 |
| [docs/ralph_parity_contract_v1.md](./docs/ralph_parity_contract_v1.md) | Parity 行为契约 |
| [docs/ralph_roadmap_milestones.md](./docs/ralph_roadmap_milestones.md) | M0–M6 里程碑与 M6 进化可审计 |
| [成长路线图.md](./成长路线图.md) | 阶段成长目标与验证标准 |
| [docs/MAINLINE_STATUS.md](./docs/MAINLINE_STATUS.md) | **主线进度快照**（问进度时更新） |

## 合并前

```bash
./run_ralph_tier0.sh
```

与 pre-push / CI 一致（见 `docs/ralph_tiers.md`）。
