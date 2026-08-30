# IR-20260520 — Mixin split incident (recovery checklist)

**Trigger:** `bccad39` (E-002/E-003 gateway/agent mixin split) → missing cross-module imports → `NameError` → Recovery **Level 3 TRUNCATE** amplified data loss in **in-memory** `conversation_history`.

**Not the same as d7 (E-004 CLI_CONFIG):** d7 code was still queued; do not mix incident fixes with E-004/E-005 PRs.

**最近更新：** 2026-05-20 — **Phase 3c Go**（飞书 read_file 成功）；事故工程线可关；Phase 4–5 另排。

---

## 授权范围（2026-05-20）

| 已授权 | 未默认执行（除非你另说） |
|--------|-------------------------|
| 完成 `exec_mixin` 遗漏 import 并 **commit** | `git push`（本地 commit 栈准备好，你回来一句「push」即可） |
| `./run_ralph_tier0.sh` + M6 `evolution_log` | 改 `data/persistent.json` / `cross-session-context.md` |
| 更新本文与 `SPLIT_PLAN` 完成定义 | Phase 4 数据恢复自动灌回 `conversation_history` |
| 新增/扩展 parity 测试门禁 | 再拆 mixin 或合入 E-004/E-005 |

---

## 事故修复 commit 栈（本地 main，按顺序）

| Commit | 内容 |
|--------|------|
| `44061e2` | Recovery 护栏、`_shared.py`、`command_handlers` 缩进、`func_name` 日志 |
| `3c8e5a1` | M6 evolution |
| `ff5021a` | Phase 3：Gate1 mixin import + recovery/gateway smoke 测试 + IR 初版 |
| `02ba615` | M6 evolution |
| *待提交* | `exec_mixin`：`ToolError` + `tools.registry` + `functools` + `_tool_executor` + `test_exec_mixin_imports.py` |

**运行时代码真源：** `~/src/MimirAether` + `MIMIR_AETHER_HOME=~/.mimiraether`。

---

## 工程阶段总览

| Phase | 状态 | 说明 |
|-------|------|------|
| **1–2** | Done | 止血 + Recovery 禁止对代码错误 TRUNCATE |
| **3** | Done | Gate1 + smoke 测试 + `SPLIT_PLAN` 完成定义 |
| **3b** | Done (`4ff3e91`) | `exec_mixin` 拆文件遗漏（见下表） |
| **3c 验收** | **Go** | 飞书 read_file AGENTS.md 成功；工具管道稳定 |
| **4** | Open | session_count 真源、jsonl 叙事（不自动灌 memory） |
| **5** | Blocked on 3c Go | E-004+ d7，**单独 PR** |

### exec_mixin 错误链（已全部在代码里修）

| # | 日志错误 | 修复 |
|---|----------|------|
| 1 | `KeyError: 'name'`（日志行） | `func_name` 打日志 |
| 2 | `ToolError` not defined | `from agent.types import ToolError` |
| 3 | `ToolRegistry` has no attribute `registry` | `import tools.registry as _tool_registry_module` |
| 4 | `functools` not defined | `import functools` + `_tool_executor` |

---

## Go / No-Go（事故线关闭标准）

全部满足 → **事故工程线可关**；Phase 4/5 可并行排期。

### 自动（Cursor 已做 / 将做）

- [x] `./run_ralph_tier0.sh` 全绿（含 `test_exec_mixin_imports.py`）
- [x] `exec_mixin` 修复 commit + M6 行
- [x] 本文 **Phase 3c** 勾选更新（2026-05-20 飞书验收）

### 你不在电脑前时 — 给 Mimir 或回来后 5 分钟（**已完成 3c**）

```bash
# 1) 硬重启（与 mimir-restart 技能相同）
cd ~/src/MimirAether
git pull   # 若已在别机 push；否则用本地 main 即可
MIMIR_AETHER_HOME=~/.mimiraether ./scripts/restart_gateway_hard.sh

# 2) 基线（应冻结在 19，除非 context 真溢出）
grep -c 'Level 3 TRUNCATE' ~/.mimiraether/logs/agent.log

# 3) 飞书 → mimiraether bot，发普通对话（非 /status）：
#    「用 read_file 读 ~/src/MimirAether/AGENTS.md 前 20 行并一句话摘要。」

# 4) 验收
tail -50 ~/.mimiraether/logs/agent.log | grep -E 'turn [12]:|Tool execution failed|NameError|TRUNCATE|functools|registry'
```

| 检查项 | Go |
|--------|-----|
| `pgrep -af gateway/run.py` 有 PID | x |
| 日志 `feishu connected` | x |
| `turn 1: … N tools`（N≥1） | x |
| **无** `Tool execution failed` | x |
| TRUNCATE 计数仍 **19**（或仅 context 类错误才增） | x |
| 飞书收到 read_file 摘要（非纯上下文编造） | x |

### 可选 push（你授权后可执行）

```bash
cd ~/src/MimirAether
git push origin main   # 或你的事故修复分支
```

---

## Mimir 离线任务包（复制即用）

```
任务：IR-20260520 事故线验收（只读 + 一条飞书消息）
仓库：~/src/MimirAether，运行时 ~/.mimiraether
禁止：再改 mixin 架构、提交 data/persistent.json

1. git log -5 --oneline  # 应含 44061e2、ff5021a、exec_mixin 修复 commit
2. ./run_ralph_tier0.sh  # 若未绿，只报告不擅自大改
3. MIMIR_AETHER_HOME=~/.mimiraether ./scripts/restart_gateway_hard.sh
4. 飞书发 tool 消息（read_file AGENTS.md 前 20 行）
5. grep TRUNCATE 计数 + tail agent.log
6. 在 docs/MIMIR_INCIDENT_IR-20260520.md 勾选 Go 表，或回复刘哥：Go/No-Go + 日志片段
```

---

## What was lost vs preserved

| Layer | Status | Notes |
|-------|--------|-------|
| `~/.mimiraether/data/sessions/*.jsonl` | Preserved | ~34 files; source for narrative recovery |
| `persistent.json` / soul | Mostly intact | `session_count` may disagree with `cross-session-context.md` |
| In-memory history (active Feishu thread) | **Damaged** | Log showed inject ~58 → 2 on 2026-05-20 |
| Tools “100% KeyError: name” | Misleading | 实为 import 链 + TRUNCATE 放大 |

## Phase 4–5（事故线之后）

| Phase | 动作 |
|-------|------|
| **4** | 统一 `session_count`（447 vs 352 vs repo 镜像）；ISSUES 一行；**不**自动把 jsonl 灌回 `conversation_history` |
| **5** | E-004 `CLI_CONFIG` → E-005 → E-008 删 `cli.py`（各自 PR，tier0 绿） |

## References

- HTML: `$WORKSPACE/mimir-crash-report-2026-05-20.html`
- Wiki commentary: `docs/MIMIR_D17_WIKI_AUDIT_COMMENTARY.md`
- Mimir tasks: `docs/MIMIR_D17_AUDIT_AND_TASKS.md`
- Restart skill: `$WORKSPACE/skills/mimir-restart/SKILL.md`
- Ops: `docs/OPERATIONS_GATEWAY.md` §2.1
