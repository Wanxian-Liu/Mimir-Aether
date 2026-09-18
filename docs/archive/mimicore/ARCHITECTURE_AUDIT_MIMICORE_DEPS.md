# Mimicore 依赖摸底

**日期**：2026-05-21  
**来源**：EV-A02（琬弦架构方案方向二 — Mimicore 服务化解耦 P1）

> **Mimicore 真源（2026-05-24）** → [`docs/phase0/mimicore-import-audit.md`](./phase0/mimicore-import-audit.md)。下文为历史快照（含已废弃 `cli.py` 顶层 import）。

## 全部 import 清单

| # | 文件 | 导入了什么 | 频率 | 类别 |
|---|------|-----------|:--:|------|
| 1 | `tools/mimircore_tool.py` | `capsule_generator.CapsuleGenerator, CapsuleType` | 延迟导入 | 🔴 在线阻塞 |
| 2 | `cli.py` | `config.model_defaults.get_model` | 顶层 | 🔴 CLI 入口 |
| 3 | `api_service.py` | `config.model_defaults.get_model` | 顶层 | 🔴 API 服务 |
| 4 | `acp_adapter/server.py` | `__version__` | 顶层 | 🟡 ACP 适配器 |
| 5 | `acp_adapter/session.py` | `config.loader.load_config` | 延迟 | 🟡 ACP 适配器 |
| 6 | `skills/mimiraether/mimiraether-self_evolution/__init__.py` | `evolve.three_ring_architecture.ThreeRingClosedLoop` | 顶层 | 🟡 技能 |
| 7 | `activate_self_evolution.py` | `evolve.three_ring_architecture` + `evolve.self_drive_engine` | 顶层 | 🟢 独立脚本 |
| 8 | `scripts/diag_capsule.py` | `capsule_generator.CapsuleGenerator` | 延迟 | 🟢 诊断脚本 |
| 9 | `scripts/migrate_capsules_batch.py` | (仅注释引用路径) | — | 🟢 迁移脚本 |
| 10 | `scripts/step3_append_generate_and_evaluate.py` | `capsule_generator.CapsuleGenerator` | 延迟 | 🟢 评估脚本 |
| 11 | `scripts/gen_and_score.py` | `capsule_generator.CapsuleGenerator` | 延迟 | 🟢 评分脚本 |
| 12 | `scripts/eval_capsule_gdi.py` | `capsule_generator.CapsuleGenerator` | 延迟 | 🟢 评估脚本 |
| 13 | `run_capsule_script.py` | `capsule_generator.CapsuleGenerator` | 顶层 | 🟢 运行脚本 |
| 14 | `run_subagent_capsule.py` | `capsule_generator.CapsuleGenerator` | 顶层 | 🟢 运行脚本 |
| 15 | `run_capsule_mimir_hermes.py` | `capsule_generator.CapsuleGenerator` | 顶层 | 🟢 运行脚本 |
| 16 | `test_fix_2_dangerous_cmd.py` | `mini_agent.hooks.DefaultBeforeToolCallHook` | 顶层 | 🟢 测试 |
| 17 | `test_fix_3_fence.py` | `gateway.gateway.fence_checkpoint` | 顶层 | 🟢 测试 |

## 阻塞性判定

| 类别 | 计数 | 在线阻塞？ | 说明 |
|------|:--:|:--:|------|
| 🔴 在线阻塞 | 2 | ✅ 是 | `mimircore_tool.py`（延迟导入，实际不阻塞启动）/ `cli.py`（顶层导入） |
| 🟡 辅助引入 | 3 | ⚠️ 可能 | ACP adapter + self_evolution skill |
| 🟢 离线/脚本 | 10 | ❌ 否 | scripts + test files |

## 关键发现

| 维度 | 结论 |
|------|------|
| Mimicore 是否在 Mimir 运行时被调用？ | ✅ 是 — `tools/mimircore_tool.py` 在 produce_capsule 时调用 capsule_generator |
| 调用频率 | 低 — 仅在 produce_capsule 时（非热路径） |
| 阻塞启动？ | ❌ — 使用延迟导入 (`from mimicore.capsule_generator import ...` inside function) |
| 最大依赖面 | `capsule_generator` — 8 处引用，全部是独立脚本或延迟导入 |

## 对方向二（Mimicore 服务化）的影响

**论证支持度：中等** — Mimicore 在线调用仅 2 处且都是延迟导入，不阻塞启动。服务化的主要收益是"代码整洁"而非"稳定性提升"。45K 行的 Mimicore 子模块虽然大，但实际在线调用路径极短且低频。

建议方向二优先级从 P1 降为 P2：先做方向一（Agent Core 重划）和方向三（Memory 语义化），Mimicore 服务化在第三步。
