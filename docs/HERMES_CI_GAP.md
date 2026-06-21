# Hermes CI — 刻意不做清单

本文件记录 Hermes Agent 仓库的 16 个 GitHub Actions workflow，
以及我们（MimirAether）**刻意不做**每项的理由。

**原则**：最小 CI 覆盖，不复制不必要的基础设施。合并门禁唯一真源：`./run_ralph_tier0.sh`（[`ralph.yml`](../.github/workflows/ralph.yml)）。

---

## 我们已有的

| 工作流 | 说明 | 状态 |
|--------|------|:----:|
| [`ralph.yml`](../.github/workflows/ralph.yml) | Ralph Tier-0 合并门禁（Gate1 编译/导入 + Gate2 pytest + Gate3 e2e） | ✅ **真源** |
| [`pytest-wide.yml`](../.github/workflows/pytest-wide.yml) | 可选宽回归 pytest（不阻塞合并） | ✅ 已有 |
| [`lint.yml`](../.github/workflows/lint.yml) | 最小 lint（pyflakes，建议性，不阻塞） | ✅ **HC-02 新增** |

---

## Hermes 16 工作流 — 刻意不做

| # | 文件名 | Hermes 用途 | 不做理由 |
|:-:|--------|-----------|---------|
| 1 | `contributor-check.yml` | CLA / 贡献者检查 | 单开发者项目，不需要 |
| 2 | `deploy-site.yml` | 文档站部署 | 无独立文档站（docs/ 是仓库内 Markdown） |
| 3 | `docker-lint.yml` | Dockerfile lint | 当前无 Docker 部署，Docker 化在 icebox（HC-22） |
| 4 | `docker-publish.yml` | Docker 镜像发布 | 同上 |
| 5 | `docs-site-checks.yml` | 文档站健康检查 | 无文档站 |
| 6 | `history-check.yml` | Git 历史审计 | 单开发者项目，不需要 |
| 7 | `lint.yml` | ruff + ty diff lint | **我们做了**（minimal 版 pyflakes） |
| 8 | `nix-lockfile-fix.yml` | Nix lockfile 自动修复 | 不使用 Nix |
| 9 | `nix.yml` | Nix 构建 | 不使用 Nix |
| 10 | `osv-scanner.yml` | 开源漏洞扫描 | 延迟（可手动触发，非阻断需求） |
| 11 | `skills-index-freshness.yml` | 技能索引时效性检查 | 技能由 `skill_manage` 工具管理，不等同于 Hermes 目录扫描 |
| 12 | `skills-index.yml` | 技能索引构建 | 同上 |
| 13 | `supply-chain-audit.yml` | 供应链安全审计 | 延迟（暂无数十万用户或发布包） |
| 14 | `tests.yml` | 全测试套件 | ✅ **已有替代**：`ralph.yml`（合并门禁）+ `pytest-wide.yml`（可选） |
| 15 | `upload_to_pypi.yml` | PyPI 发布 | 不发布到 PyPI |
| 16 | `uv-lockfile-check.yml` | uv lockfile 检查 | 不使用 uv |

---

## 何时重新评估

以下条件任一满足时，重新评估对应工作流：

- **HC-22（Docker）拍板** → 重新评估 docker-lint / docker-publish
- **项目确认漏洞扫描需求** → 重新评估 osv-scanner / supply-chain-audit
- **确认使用 Nix 或 uv** → 重新评估对应的 lockfile 工作流
- **有文档站需求** → 重新评估 deploy-site / docs-site-checks

除非上述条件触发，否则这些工作流**不做**是刻意设计，不是遗漏。
