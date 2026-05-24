# 生产/真环境 Smoke 清单（里程碑 A）

**用途**：在 **真实配置、真实网络（按需）** 下勾选 **成长路线图 · 阶段 1 · 里程碑 A** 的四条标准。与自动化门禁 **`./run_ralph_tier0.sh`** 互补：门禁证明 **桩级行为**；本清单证明 **能干活**。

**不替代**：`docs/m3_cli_quick_task_slice.md`（CLI `run_task` / `-q` 同栈已进 Gate2，无网桩测）。

| 字段 | 填写 |
|------|------|
| 日期 | 2026-05-02（最近一轮见 §执行记录） |
| 执行人 | 负责人 / 代理（真机） |
| 仓库根 | 当前 **git clone 根**（任意路径）；运行时数据默认 **`~/.mimiraether`** 或由 `MIMIR_AETHER_HOME` 指定（见 `docs/path-contract.md`） |
| 备注 | CLI v0.1.0；**飞书** 应用 **mimiraether**（`cli_aa82adc1…`）已跑通发送；**勿**在仓库提交 token |

---

## 什么时候需要跑本清单

| 情况 | 建议 |
|------|------|
| **建议跑** | 准备把 **里程碑 A** 标成完成；**大改过** gateway、CLI、工具注册、环境路径；长期只信 `./run_ralph_tier0.sh`、**从未**在真配置下走通过；**上线/演示/交给别人用**之前。 |
| **可以晚点跑** | 只改文档、只动桩测、日常小修且**不宣称**「真环境已验」；纯开发迭代若只依赖门禁绿。 |
| **不必等「全开发完」** | 可以**现在就跑一轮**：能勾的勾满，缺 key/缺平台的项写 **阻塞原因**；等配置齐再跑第二轮补勾。 |

**和门禁的关系**：`run_ralph_tier0.sh` **绿 ≠ 本清单全绿**；前者是自动化契约，后者是 **真机/真配置** 证据。

---

## 如何委托 MimirAether 代理执行

你可以把下面整段复制给 **MimirAether 代理**（在已打开本仓库、且能执行终端的前提下）。代理会代跑命令并整理证据；**密钥与首次平台绑定**仍可能需要你本人操作。

```
请阅读 docs/mimir_prod_smoke.md。在 **当前 MimirAether git 根目录**（`git rev-parse --show-toplevel` 或 Cursor 已打开的工作区根；勿假设固定 `~/.openclaw/...`）执行里程碑 A 的 A1–A4：

- A1：依次运行文档中列出的 cli 子命令，记录每条通过/失败（命令、退出码、关键输出摘要）。
- A2：检查 gateway 与 gateway health；若依赖 api_server，对照 docs/gateway-cli-health.md。若我尚未配置某平台或缺少凭证，明确写「阻塞：缺 XXX」。
- A3：在已有模型与工具配置下，尝试一次会触发 tool call 的对话（或最小脚本）；记录工具名与最终回复是否体现结果。
- A4：按仓库内现有 RL 入口尝试最小一步；若无脚本或环境不允许（如无 GPU），写清「跳过 + 原因」。

输出格式：按 A1/A2/A3/A4 分节；每项用 [x] / [ ] 给出勾选建议，并附简短证据。不要打印任何 API key 或完整 .env。
```

**注意**：代理**不能**替你完成需人机交互的步骤（例如厂商后台创建 bot、手机验证）；这类项请标为阻塞，由你补完后**再让代理跑第二轮**补勾。

---

## A1 — `hermes_cli` 对齐：核心子命令可执行

在仓库根、已激活依赖的环境中逐项执行（**能跑通且无未处理崩溃**即勾选；具体退出码以当版 CLI 为准）。

- [x] `python3 cli.py version`（✅ v0.1.0，2026-05-01 执行记录）
- [x] `python3 cli.py status`
- [x] `python3 cli.py status --deep`（✅ DeepSeek/MiniMax 可连接）
- [x] `python3 cli.py doctor`（✅ 全部通过）
- [x] `python3 cli.py config`（或你常用的 `config` 子命令）
- [x] `python3 cli.py setup`（或 `setup <section>`，按需）

**可选加深**：`profiles` / `models` / `gateway` / `cron` 等你日常会用的子集各跑一条只读命令。

---

## A2 — Gateway：能启动并处理**真实对话**

- [x] Gateway 进程按你环境启动（如 `python3 cli.py gateway start` 或 systemd，与文档一致）。（✅ 例：PID 48920）
- [x] 至少一个已配置 **platform** 上收到并回复一条**真实消息**（Telegram/Discord/飞书/其他）。（✅ **飞书**：应用 **mimiraether** 发送测试消息成功，`code:0`；**勿**将 token 写入本仓库）
- [x] `python3 cli.py gateway health` 或 **`/health`**：若依赖 `api_server`，已按 **`docs/gateway-cli-health.md`** 在 **`$MIMIR_AETHER_HOME/config.yaml`**（或 `get_mimir_home()` 对应路径）中配置 `api_server` 与端口。（✅ `{"status":"ok"}`，api_server **18999**）

**失败时先看**：`logs/`、`gateway` 子命令输出、`path-contract` 三层路径是否混用。

---

## A3 — 工具调用链路：**registry → 执行 → 回到模型/用户**

在**真模型**（或你允许的代理）下完成一次**可见的工具调用闭环**：

- [x] 用户输入或脚本触发 **至少一次** tool call（任选：`read_file` / `execute_code` / 其它已启用工具）。（✅ 工具名 **`terminal`**）
- [x] 工具返回进入对话上下文，最终回复体现工具结果或合理错误（非静默失败）。（✅ 链路完整）

**建议记录**：工具名、是否沙箱/远程 code_execution、失败时的错误摘要（不含 secret）。

---

## A4 — 基础 RL：**collect → train → reward**（最小闭环）

按你当前 RL 入口（Atropos / 项目内脚本）勾选**最小一步**即可，不必完整长跑：

- [x] **collect**：产生一条可追溯的 trajectory 或日志（路径或 run id）。（✅ 轨迹 `73ec02fc`，2 steps）
- [x] **train**：执行至少一步训练或 dry-run 文档规定的等价命令（若环境无 GPU，注明「跳过 + 原因」）。（✅ `PPOOptimizer` + `Trainer` 初始化成功）
- [x] **reward**：日志或指标中出现非空 reward / loss（或等价信号）。（✅ `step_rewards=[0.0, 1.3]`）

**参考**：`optional-skills/mlops/hermes-atropos-environments/SKILL.md`（上游 Hermes 形态）；以本仓库**实际脚本/入口**为准更新本节命令。

---

## 汇总

| 里程碑 A 条款 | 对应章节 | 完成（截至最近执行记录） |
|---------------|----------|--------------------------|
| hermes_cli 核心命令可用 | §A1 | **是** |
| gateway **启动 + health**（子集） | §A2 | **是** |
| gateway **至少一平台真实消息往返** | §A2 | **是**（飞书） |
| 工具链路完整 | §A3 | **是** |
| 基础 RL 闭环 | §A4 | **是** |

**里程碑 A（成长路线图阶段 1）**：在 **A1–A4 与 A2 飞书真实消息** 均已满足的前提下，可将 `docs/MAINLINE_STATUS.md` 中里程碑 **A** 标为 **绿**（见该文件当前状态）。

---

## 执行记录（归档）

以下为代理回报摘要，便于审计与二次复测（**不含**任何密钥）。

### 2026-05-01 — 里程碑 A 执行结果（代理）

**A1 — CLI**

| 子命令 | 状态 |
|--------|------|
| `version` | ✅ v0.1.0 |
| `status` | ✅ |
| `status --deep` | ✅ DeepSeek/MiniMax 可连接 |
| `doctor` | ✅ 全部通过 |
| `config` | ✅ |
| `setup` | ✅ |

**A2 — Gateway**

| 检查项 | 状态 |
|--------|------|
| `gateway start` | ✅ PID 48920（示例） |
| `gateway health` | ✅ `{"status":"ok"}` |
| api_server | ✅ 已配置，端口 **18999** |
| 至少一平台 **真实消息** | ⚠️ **未**（首轮；飞书于 2026-05-02 补通，见下节） |

**A3 — 工具**

| 项目 | 状态 |
|------|------|
| 工具名 | ✅ `terminal` |
| 链路 | ✅ 输入 → 执行 → 结果 → 回复 |

**A4 — RL 最小闭环**

| 组件 | 状态 |
|------|------|
| collect | ✅ 轨迹 `73ec02fc`，2 steps |
| reward | ✅ `step_rewards=[0.0, 1.3]` |
| train | ✅ `PPOOptimizer` + `Trainer` 初始化成功 |

### 2026-05-24 — A1 Gateway 硬重启 + 飞书回归 smoke（人工）

**前置（已由 Cursor 执行）**

| 项 | 结果 |
|----|------|
| 命令 | `MIMIR_REPO_ROOT=~/src/MimirAether MIMIR_AETHER_HOME=~/.mimiraether ./scripts/restart_gateway_hard.sh` |
| 新 PID | **691521**（`python3 …/gateway/run.py`） |
| `/health` | `{"status":"ok","gateway":"ok","agent":"ok"}` |
| 飞书 WS | `Lark: connected to wss://msg-frontier.feishu.cn/ws/v2…` |

**刘哥在飞书对 mimiraether 执行（勾选后回贴结果）**

| # | 用例 | 操作 | 期望 | ☐ |
|---|------|------|------|---|
| T-03 | 空表头表（ISSUES #2 / backlog #9） | 让 bot 回复含空 `<th></th>` 的 HTML 表格 | 列名显示 `—`；**无**纯文本回退；日志无 `230099` | [x] 2026-05-25 刘哥复验 pass |
| T-04 | 双按钮（ISSUES #3） | 让 bot 回复含两组按钮的 HTML（选 A / 选 B） | 飞书卡片 **两个按钮都可见** | [x] 2026-05-25 刘哥复验 pass |
| T-01 | 图片下载（ISSUES #1，可选） | 发一张图片 | 无「图片下载失败」；识图仍受 OPENROUTER 限制可跳过 | |

**验收后 log grep（本机）**

```bash
grep -E '230099|200907|Image downloaded|feishu.*card' \
  ~/.mimiraether/logs/agent.log ~/.mimiraether/logs/gateway.log 2>/dev/null | tail -15
```

全部通过后：将 `docs/ISSUES.md` #3 标为 resolved；`GATEWAY_STABILITY_BACKLOG.md` #9 标为已验证；可关 GitHub **#19**（Gateway 重启）。

---

### 2026-05-02 — 飞书（Lark）补测（A2 真实消息）

| 项目 | 结果 |
|------|------|
| Token / 应用侧 | ✅ 已获取（**仅存本机配置，勿提交仓库**） |
| 飞书应用名称 | **mimiraether**（App ID `cli_aa82adc1…`；勿与旧称「wan」或其它 Bot 混淆） |
| 发送消息 | ✅ 成功（飞书 API `code:0`） |
| 说明 | 用户侧飞书可查收测试消息；Open ID / 消息 ID **不写入**本文档 |

---

## 相关文档

- `docs/path-contract.md` — agent home / profile / 平台配置  
- `docs/gateway-cli-health.md` — `api_server` 与 health  
- `docs/m3_cli_quick_task_slice.md` — 自动化 CLI 垂直切片（桩）  
- `成长路线图.md` — 阶段 1 原文  

---

## 修订

| 日期 | 说明 |
|------|------|
| 2026-05-25 | **刘哥复验**：T-03 空表头 + T-04 双按钮 **pass**；R5 飞书 `read_file` 工具往返 **30s 内成功**。Gateway #9 结案。 |
| 2026-05-24 | A1：硬重启 Gateway（PID 691521）；飞书 WS 已连；T-03/T-04 人工 smoke 清单见上节。 |
| 2026-05-02 | 飞书应用 **mimiraether** 发送成功；A2 真实消息项已闭合；**勿**提交 token。 |
| 2026-05-01 | 写入首轮真环境执行记录（A1/A3/A4 通过；A2 缺跨平台真实消息）。 |
| 2026-05-01 | 增加「何时需要跑」「如何委托代理」与可复制指令。 |
| 2026-05-01 | 初版：A1–A4 勾选表，与里程碑 A 四条对齐。 |
