# CI：子模块与 Ralph 门禁排障

Ralph 工作流 [`.github/workflows/ralph.yml`](../.github/workflows/ralph.yml) 在跑 `./run_ralph_tier0.sh` 前会执行 `git submodule update --init --recursive`。

## 常见失败：子模块拉取失败

1. **检查 `.gitmodules`**  
   确认子模块 URL 与权限模型一致（HTTPS vs SSH）。

2. **仓库 Secret：`SUBMODULE_PAT`**（可选但常见）  
   若子模块为私有或需鉴权，在 GitHub **Settings → Secrets and variables → Actions** 中配置 `SUBMODULE_PAT`（对子模块仓库有读权限的 fine-grained 或 classic PAT）。  
   Workflow 会用其改写 `https://github.com/` 的凭据前缀（见 `ralph.yml` 中 `Init git submodules` 步骤）。

3. **本地复现**  
   ```bash
   git submodule sync --recursive
   git submodule update --init --recursive --depth 1
   ./run_ralph_tier0.sh
   ```

4. **非子模块问题**  
   若子模块已成功但仍失败，再看 Gate1 缺少依赖：按 `ralph.yml` 注释将缺失包加入 [`requirements-ci.txt`](../requirements-ci.txt)。

## 相关文档

- 运行契约：[`MIMIR_RUNTIME_CONTRACT.md`](./MIMIR_RUNTIME_CONTRACT.md)
- 路径约定：[`path-contract.md`](./path-contract.md)
