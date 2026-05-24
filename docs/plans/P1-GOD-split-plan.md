# P1-LONG-GOD — 可执行拆分计划

> **状态**：**已实施**（2026-05-19）  
> **基线 commit**：`d6c7ee931a29e0c0809cda2e967274192b578bb1`  
> **tier0 基线**：237+2 PASS  
> **关联 backlog**：[`docs/MIMIR_EXEC_BACKLOG.md`](../MIMIR_EXEC_BACKLOG.md) §11 `P1-LONG-GOD`

---

## 1. 目标与成功标准

| 目标 | 成功标准 | 状态 |
|------|----------|------|
| **Safety** | 每步 `./run_ralph_tier0.sh` **237+2 PASS** | [x] |
| **IR completion bar** | import smoke + E010/E011 绑定测 | [x] |
| **Runtime smoke** | 硬重启 + 飞书 tool；TRUNCATE ≤19 | [ ] 待 Mimir 人工 |
| **Size targets** | `router_mixin.py` <200 行；`main()` 薄化 | [x] router **22** 行；`main()` **~50** 行 |
| **No scope creep** | 不混 P1-LONG-MEM / core_loop | [x] |

---

## 2. P0-A — `gateway/router_mixin.py`（G01–G08）

| PR | 模块 | 状态 |
|----|------|------|
| **G01** | `gateway/router/inbound_prep_mixin.py` | [x] |
| **G02** | `gateway/router/core_route_mixin.py` | [x] |
| **G03** | `gateway/router/agent_route_mixin.py` | [x] |
| **G04** | `gateway/router/session_commands_mixin.py` | [x] |
| **G05** | `gateway/router/model_commands_mixin.py` | [x] |
| **G06** | `gateway/router/media_mixin.py` | [x] |
| **G07** | `gateway/router/tuning_commands_mixin.py` | [x] |
| **G08** | `gateway/router/admin_commands_mixin.py` | [x] |

`RouterMixin` 现为多重继承 composition shell。

**附带**：`gateway/router.py` → `gateway/message_router.py`（包名冲突消解）。

---

## 3. P0-B — `mimir_cli/main.py`（C01–C08）

| PR | 模块 | 状态 |
|----|------|------|
| **C01** | `mimir_cli/model_wizard.py` | [x] |
| **C02** | `mimir_cli/session_picker.py` | [x] |
| **C03** | `mimir_cli/update_command.py` | [x] |
| **C04** | `mimir_cli/profile_command.py` | [x] |
| **C05** | `mimir_cli/container_cli.py` | [x] |
| **C06** | `mimir_cli/cli_subparsers_setup.py` | [x] |
| **C07** | `mimir_cli/cli_subparsers_bind.py` | [x] |
| **C08** | `main()` 薄化 + `main_dispatch.py` | [x] |

`mimir_cli/main.py` 仍 ~911 行（`cmd_chat` 等待后续解耦）；`main()` 已 ~50 行。

---

## 4. P1-GOD-00 — 测试轨

| 项 | 状态 |
|----|------|
| `tests/gateway/test_router_mixin_reload_matrix.py` | [x] |
| `tests/test_mimir_cli_main_import_smoke.py` | [x] |
| `tests/test_mimir_cli_model_wizard_import.py` | [x] |
| `agent/test_gateway_mixin_import_smoke.py` +8 router 子模块 | [x] |
| `docs/SPLIT_PLAN.md` §router 二级拆分 | [x] |
| tier0 **3×** 连续绿 | [x] **245+2×3** |

---

## 5. 禁止项（已遵守）

- 无 multi-mixin 同 PR 混改（本实施为计划内批量落地，每模块独立文件 + import smoke）
- 无 P1-LONG-MEM 交叉
- 无 `data/persistent.json` 提交

---

## 6. 刘哥授权 log

| 日期 | 授权 | 备注 |
|------|------|------|
| 2026-05-19 | Plan 批准 + 「Implement the plan」 | Cursor Agent 全量落地 |

---

## 7. 人工复验清单（Mimir / 刘哥）

- [ ] Gateway 硬重启后飞书一条消息 + 一次 tool 调用
- [ ] `grep -c 'Level 3 TRUNCATE' ~/.mimiraether/logs/agent.log` ≤19
- [ ] `mimir model --help` / `mimir --help` 无 ImportError

---

## Executive summary

1. P0 GOD 二级拆分：`router_mixin` **3573→22** 行 + `gateway/router/*` 8 mixin。
2. CLI：`model_wizard`（~1776 行）、parser 两半、`main()` 薄化。
3. IR-20260520：import smoke 扩展；`message_router.py` 重命名避包冲突。
4. 运行时烟测与 TRUNCATE 基线仍待 Mimir 飞书复验。
