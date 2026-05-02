# 生产/真环境 Smoke 清单（里程碑 A）

**用途**：在 **真实配置、真实网络（按需）** 下勾选 **成长路线图 · 阶段 1 · 里程碑 A** 的四条标准。与自动化门禁 **`./run_ralph_tier0.sh`** 互补：门禁证明 **桩级行为**；本清单证明 **能干活**。

**不替代**：`docs/m3_cli_quick_task_slice.md`（CLI `run_task` / `-q` 同栈已进 Gate2，无网桩测）。

| 字段 | 填写 |
|------|------|
| 日期 | |
| 执行人 | |
| 仓库根 | 默认 `~/.openclaw/projects/MimirAether`（见 `docs/path-contract.md`） |
| 备注 | 版本/commit、所用模型、是否 staging |

---

## A1 — `hermes_cli` 对齐：核心子命令可执行

在仓库根、已激活依赖的环境中逐项执行（**能跑通且无未处理崩溃**即勾选；具体退出码以当版 CLI 为准）。

- [ ] `python3 cli.py version`
- [ ] `python3 cli.py status`
- [ ] `python3 cli.py status --deep`（会探测外网/API，需 key 时注明）
- [ ] `python3 cli.py doctor`（可加 `--fix` 若你接受其副作用）
- [ ] `python3 cli.py config`（或你常用的 `config` 子命令）
- [ ] `python3 cli.py setup`（或 `setup <section>`，按需）

**可选加深**：`profiles` / `models` / `gateway` / `cron` 等你日常会用的子集各跑一条只读命令。

---

## A2 — Gateway：能启动并处理**真实对话**

- [ ] Gateway 进程按你环境启动（如 `python3 cli.py gateway start` 或 systemd，与文档一致）。
- [ ] 至少一个已配置 **platform** 上收到并回复一条**真实消息**（Telegram/Discord/其他）。
- [ ] `python3 cli.py gateway health` 或 **`/health`**：若依赖 `api_server`，已按 **`docs/gateway-cli-health.md`** 配置 `~/.openclaw/config.yaml` 中 `api_server` 与端口。

**失败时先看**：`logs/`、`gateway` 子命令输出、`path-contract` 三层路径是否混用。

---

## A3 — 工具调用链路：**registry → 执行 → 回到模型/用户**

在**真模型**（或你允许的代理）下完成一次**可见的工具调用闭环**：

- [ ] 用户输入或脚本触发 **至少一次** tool call（任选：`read_file` / `execute_code` / 其它已启用工具）。
- [ ] 工具返回进入对话上下文，最终回复体现工具结果或合理错误（非静默失败）。

**建议记录**：工具名、是否沙箱/远程 code_execution、失败时的错误摘要（不含 secret）。

---

## A4 — 基础 RL：**collect → train → reward**（最小闭环）

按你当前 RL 入口（Atropos / 项目内脚本）勾选**最小一步**即可，不必完整长跑：

- [ ] **collect**：产生一条可追溯的 trajectory 或日志（路径或 run id）。
- [ ] **train**：执行至少一步训练或 dry-run 文档规定的等价命令（若环境无 GPU，注明「跳过 + 原因」）。
- [ ] **reward**：日志或指标中出现非空 reward / loss（或等价信号）。

**参考**：`optional-skills/mlops/hermes-atropos-environments/SKILL.md`（上游 Hermes 形态）；以本仓库**实际脚本/入口**为准更新本节命令。

---

## 汇总

| 里程碑 A 条款 | 对应章节 | 完成 |
|---------------|----------|------|
| hermes_cli 核心命令可用 | §A1 | ☐ |
| gateway 真实对话 | §A2 | ☐ |
| 工具链路完整 | §A3 | ☐ |
| 基础 RL 闭环 | §A4 | ☐ |

**四格均勾选** → 可将 `docs/MAINLINE_STATUS.md` 中阶段 1 / 里程碑 A 从 **黄** 调整为 **绿**（并写更新日志）。

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
| 2026-05-01 | 初版：A1–A4 勾选表，与里程碑 A 四条对齐。 |
