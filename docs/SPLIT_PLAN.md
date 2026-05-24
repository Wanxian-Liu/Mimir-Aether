# GOD 拆分 — 精确边界

> 来源: gateway/run.py (9,273行)
> 策略: Mixin 类，每个独立文件，GatewayRunner 多重继承
> 每段: 创建文件 → 移动方法 → tier0绿 → 下一段

## 6 模块边界

| # | 文件 | 行范围 | 方法数 | 估计行数 |
|---|------|--------|--------|----------|
| 1 | `gateway/voice_mixin.py` | 714-772, 4878-5208 | 11 | ~450 |
| 2 | `gateway/cron_mixin.py` | 5344-5673, 6690-7032, 8809-9164 | 8 | ~600 |
| 3 | `gateway/health_mixin.py` | 1025-1120, 1391-1539, 1837-1858, 1978-2104 | 14 | ~500 |
| 4 | `gateway/session_mixin.py` | 773-891, 907-996, 1398-1426, 1859-1977, 7033-7057, 7390-7461 | 12 | ~700 |
| 5 | `gateway/router_mixin.py` | 2381-2501, 2502-3982, 3983-6597 | 35 | ~2300 |
| 6 | `gateway/agent_mixin.py` | 7058-8808 | 5 | ~1400 |

## 执行顺序

1. voice_mixin (最小,自包含) → 验证模式
2. cron_mixin → 验证定时任务正常
3. health_mixin → 验证监控心跳
4. session_mixin → 验证会话管理
5. router_mixin (最大) → 验证消息路由
6. agent_mixin → 验证Agent生命周期

每段后: run_ralph_tier0.sh 确保 162 passed

## 拆分完成定义（IR-20260520 起）

一次 mixin 拆分视为**完成**当且仅当：

1. `./run_ralph_tier0.sh` 全绿（含 Gate1 `gateway.run` + mixin import smoke）
2. `agent/test_gateway_mixin_import_smoke.py` 与 `agent/test_recovery_mixin_code_errors.py` 通过
3. 硬重启 gateway 后：飞书一条普通消息 + 一次 tool 调用无 NameError；`agent.log` 不因代码错误新增 `Level 3 TRUNCATE`

## router 二级拆分（P1-LONG-GOD · 2026-05-19）

> 可执行计划：**[`docs/plans/P1-GOD-split-plan.md`](plans/P1-GOD-split-plan.md)**  
> 基线 commit：`d6c7ee931a29e0c0809cda2e967274192b578bb1` · tier0 **237+2**

`gateway/router_mixin.py` 已降为 **composition shell**（~22 行）；实现分布在 `gateway/router/*_mixin.py`（G01–G08）：

| 模块 | 职责 |
|------|------|
| `gateway/router/inbound_prep_mixin.py` | `_prepare_inbound_message_text` |
| `gateway/router/core_route_mixin.py` | `_handle_message` |
| `gateway/router/agent_route_mixin.py` | `_handle_message_with_agent`, `_format_session_info` |
| `gateway/router/session_commands_mixin.py` | reset/profile/status/stop/restart/help/commands |
| `gateway/router/model_commands_mixin.py` | model/provider/personality/retry/undo/set_home |
| `gateway/router/media_mixin.py` | `_get_guild_id`, `_deliver_media_from_response` |
| `gateway/router/tuning_commands_mixin.py` | rollback/reasoning/fast/yolo/verbose/compress/title/resume/branch/usage/insights/reload_mcp |
| `gateway/router/admin_commands_mixin.py` | approve/deny/debug/update |

**注意**：原 `gateway/router.py`（MessageRouter）已重命名为 **`gateway/message_router.py`**，避免与 `gateway/router/` 包冲突。

**CLI 二级拆分**（C01–C08）：`mimir_cli/model_wizard.py`、`session_picker.py`、`update_command.py`、`profile_command.py`、`container_cli.py`、`cli_subparsers_setup.py`、`cli_subparsers_bind.py`；`main()` ~50 行。

**测试轨**：`tests/gateway/test_router_mixin_reload_matrix.py`、`tests/test_mimir_cli_main_import_smoke.py`、`tests/test_mimir_cli_model_wizard_import.py`；`agent/test_gateway_mixin_import_smoke.py` 扩展 8 个 router 子模块。
