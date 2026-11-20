# CODING_CONVENTIONS — 编码约定（按需读，不每轮注入）

> 定位：**实现面约定**，只在要动对应代码时才需要读。
> 为什么不进 `AGENTS.md`：AGENTS 每轮注入（token × 每轮）且承载「行为纪律/流程闸门」（完工定义、通道、边界），把编码风格混进去会稀释红线条款的可读性。本文按需读，AGENTS 不堆条文。
> 为什么不写成 ADR：ADR 记录**单次决策**的来龙去脉；本文是**持续适用**的约定，会随审计追加小节。
> 为什么不扩 `docs/TEST_NAMING_CONVENTION.md`：那份只讲测试命名，扩范围会污染其权威边界。

## 1. broad-except 与回退留痕（2026-11-20 立 · 源：B3-Y7/Y10 broad-except 治理两项）

### 1.1 约定（一条）

**允许 `except Exception`（在其有明确回退时），但回退必须留 `logger.debug` 痕。**
即：收窄不是目的，**可诊断**才是目的——异常被吞掉而无人知道「刚刚走了回退分支」，等于把故障改成静默降级。

### 1.2 四类分型（判准 · 可复用）

| 类 | 定义 | 处置 |
|---|---|---|
| C1 有日志有兜底 | 体内已有 `logger.*` 且回退值明确 | 合规，不动 |
| C2 无日志有兜底 | 体为 `pass` / 显式回退赋值 | **仅关键分叉补 `logger.debug`**（见 §1.3） |
| C3 无兜底裸吞 | 吞后下游假定成功、无降级无记账 | 必须改：要么补回退，要么上抛；挂账登记 |
| C4 级别错 | 可恢复路径用 `error` / 启动致命路径用 `debug` | 修级别（易与 C1 混淆，审计时逐处过） |

### 1.3 「关键分叉」判准（防主观 · 四域）

**回退值流入下列任一决策面 = 关键 ⇒ 必须补 `debug`：**

| 域 | 含 | 例（本仓） |
|---|---|---|
| K1 请求/会话路由 | session key、provider 选择 | `_session_key_for_source` · `detect_provider_for_model` |
| K2 模型选择与降级 | 默认模型、fallback、fast-mode、smart routing、service tier、模型目录 | `get_default_model_for_provider` · `provider_model_ids` |
| K3 降级/重试/退出时序 | backoff、drain timeout、exit budget、预取降级、命令面降级 | `drain_budget_seconds` · `request_cross_session_prefetch` |
| K4 可观测记录 | runtime status、exit record | `record_exit_event` · `write_runtime_status` |

**非关键（明确排除，防扩大化——否则「关键」会退化成「全部」）**：纯清理（`close`/`disconnect`/`cleanup_*`/shutdown_memory_provider/marker 文件）、纯展示与格式化（`session_info`/`_tip_line`/`title`）、纯 prompt 组装（prefill / ephemeral prompt）、纯展示开关（busy input mode / background notifications）。

> 一条判别捷径：**问「这次回退会不会让下一次请求走错模型 / 走错 provider / 时序错位 / 事后查不到」**——会 ⇒ 关键；只是「少显示一点东西」⇒ 非关键。

### 1.4 刷屏风险（已实测，不是估计）

- 本仓 root logger 默认 `WARNING`；stderr handler 仅在 `-v`(INFO)/`-vv`(DEBUG) 时挂载并下调级别（`gateway/run.py` verbosity 注释段）。
- 日志文件 `~/.mimiraether/logs/agent.log` 实测 **20,134 行 / 0 条 DEBUG** ⇒ 文件面当前级别 = INFO，`logger.debug` **不落盘**。
- 且 `debug` 只在 **except 命中时**产出：配置健康时每轮增量 = **0 行**。⇒ 该约定**不带来常态日志膨胀**；要看回退痕时用 `-vv` 或临时调级别。

### 1.5 判据（§8.5 形态 2 · 缺口清单可跑）

**审计辅助命令（不是 blocking 闸）**——列出「体为 `pass` 且无任何 `logger.` 调用」的站点，即 C2 待判清单：

```bash
cd ~/src/MimirAether && ~/src/MimirAether/.venv/bin/python3 - <<'PY'
import re
FILES = ["gateway/session_mixin.py", "gateway/router/session_commands_mixin.py", "mimir_cli/models.py"]
for f in FILES:
    L = open(f).read().split(chr(10))
    for i, l in enumerate(L):
        if re.match(r"\s*except Exception", l) and i + 1 < len(L) and L[i+1].strip() == "pass":
            print(f + ":" + str(i + 1))
PY
```

- **已知局限（必须一并申报）**：该命令只判「体内是不是直接 `pass`」，**不判**是否命中 K1-K4——关键/非关键仍需人判（或套 §1.3 表）。若将来要把本约定升为 **blocking 闸**（「C2 且命中 K 域而无日志 ⇒ 拦」），须落独立脚本 + 正负双向自检（§9 档位 ④）；本条当前**不自称 blocking**。
