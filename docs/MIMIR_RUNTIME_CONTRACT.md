# MimirAether 运行契约（去平台依赖）

独立部署时建议显式设置环境变量，避免隐式依赖 `~/.openclaw/`。

## 必填 / 强烈推荐

| 变量 | 说明 |
|------|------|
| `MIMIR_AETHER_HOME` | 本仓库根目录（含 `config.yaml`、`.env`、`skills/`）。**生产环境推荐始终设置。** 与旧名 `MIMIRAETHER_HOME` 同时存在时，**以本变量为准**。 |
| `HERMES_HOME` | 与 `MIMIR_AETHER_HOME` **设为同一路径**，直到所有 `hermes_cli` / `hermes_constants` 调用路径完全收敛。`scripts/start.sh` 会自动对齐。 |

未设置 `MIMIR_AETHER_HOME` 时，代码默认回退到 `~/.openclaw/projects/MimirAether`（与历史布局兼容）。

## 独立部署检查清单（习惯）

部署到**无**历史 `~/.openclaw` 环境前，建议逐项确认：

1. 已设置 **`MIMIR_AETHER_HOME`** 指向本仓库根（含 `config.yaml`、`skills/`）。
2. 已设置 **`HERMES_HOME`** 与上一步**同一路径**（或使用 [`scripts/start.sh`](../scripts/start.sh) 自动对齐）。
3. 密钥在 **`$MIMIR_AETHER_HOME/.env`**，主配置在 **`$MIMIR_AETHER_HOME/config.yaml`**。
4. 不把「机器上必须已有 OpenClaw 目录」当作前提。

## Smoke：不依赖 `~/.openclaw`（最小验证）

在**仅**设置 `MIMIR_AETHER_HOME` / `HERMES_HOME`（见上表）的机器上，可在仓库根执行下列命令（与 [`scripts/smoke_mimir_home.sh`](../scripts/smoke_mimir_home.sh) 等价）：

```bash
export MIMIR_AETHER_HOME="${MIMIR_AETHER_HOME:-$(pwd)}"
export HERMES_HOME="${HERMES_HOME:-$MIMIR_AETHER_HOME}"
./scripts/smoke_mimir_home.sh
```

或手工分步：

```bash
export MIMIR_AETHER_HOME=/path/to/MimirAether   # 本仓库根
export HERMES_HOME="$MIMIR_AETHER_HOME"
python3 -c "from mimir_constants import get_mimir_home; print('mimir_home=', get_mimir_home())"
python3 -c "from mimiraether_constants import get_mimiraether_home; print('mimiraether_home=', get_mimiraether_home())"
python3 -c "from mimicore.config.model_defaults import get_model; print('default_model=', get_model())"
python3 -c "import importlib; import mimir_constants, gateway.sticker_cache as s; importlib.reload(mimir_constants); importlib.reload(s); print('sticker_cache=', s.CACHE_PATH)"
```

（须在同一会话中已 `export MIMIR_AETHER_HOME` / `HERMES_HOME`。）最后一条在 reload 后确认 `gateway.sticker_cache.CACHE_PATH` 落在 `$MIMIR_AETHER_HOME/data/` 下。

## 配置与密钥

- **主配置**：`$MIMIR_AETHER_HOME/config.yaml`
- **密钥**：`$MIMIR_AETHER_HOME/.env`（勿提交真实密钥；见仓库根 `.env.example`；从平台 `gateway.systemd.env` 迁移见 [`GATEWAY_SYSTEMD_ENV.md`](./GATEWAY_SYSTEMD_ENV.md)）

## 与 OpenClaw 平台层的关系

- 不再要求存在 `~/.openclaw/config.yaml` 才能运行 MimirAether；若仍保留该文件，请注意与项目内 `config.yaml` 可能重复，以 **`MIMIR_AETHER_HOME` 树下文件为准**。
- 遗留变量 `OPENCLAW_*`：若仍有消费方，视为过渡兼容；新代码不应新增依赖。详见 [`OPENCLAW_ENV_LEGACY.md`](./OPENCLAW_ENV_LEGACY.md)。

## vendored `hermes_cli`

`hermes_cli/` 目录为自包含副本（MIT，来源见 `NOTICE`），供 `mimcore` 与 `agent/auxiliary_client` 等 import，**无需**将外部 `hermes-agent` 加入 `PYTHONPATH`。

闭包与入口模块清单见 `docs/hermes_cli_closure.md`。

## 贡献者：路径字面量与门禁

新增或修改默认路径时，请遵守 [`path-contract.md`](./path-contract.md)（含 `.openclaw` 字面量约定与 tier0 末尾 advisory 脚本）。

## 相关运维文档

- CI 子模块 / Ralph 失败排障：[`CI_SUBMODULE.md`](./CI_SUBMODULE.md)
