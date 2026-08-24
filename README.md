# MimirAether

![Ralph Tier-0](https://github.com/Wanxian-Liu/Mimir-Aether/actions/workflows/ralph.yml/badge.svg)
![Lint](https://github.com/Wanxian-Liu/Mimir-Aether/actions/workflows/lint.yml/badge.svg)
![Pytest wide](https://github.com/Wanxian-Liu/Mimir-Aether/actions/workflows/pytest-wide.yml/badge.svg)

自主 Agent 运行时与技能库：**代码**在任意 git clone 根目录；**运行时数据**（`.env`、`config.yaml`、`data/` 等）默认在 **`~/.mimiraether`**，或由 **`MIMIR_AETHER_HOME`** 显式指定（见 `docs/path-contract.md`、`docs/MIMIR_ACTIVATE.md`）。

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
