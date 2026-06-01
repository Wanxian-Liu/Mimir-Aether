# SELF-14: VoE + WM 快照

> Generated: 2026-06-01T08:50Z

---

## VoE (Value of Evidence) — Degeneration Guard

| 配置项 | 值 |
|--------|----|
| 来源 | LeWM (2603.19312) §3.1 + §5.2 |
| 文件 | `data/degeneration_guard.json` |
| 版本 | 1.0.0 |
| 创建时间 | 2026-05-14 |

**4 个检测信号：**

| 信号 | 阈値 | 行动 |
|------|------|------|
| loop_detection | 同工具连续 ≥3 次 / 5 轮 | warn |
| information_density | 最近 5 轮 ≥40% 需含新信息 | warn |
| context_quality | 压缩后保留率 ≥50% | compress_trigger |
| surprise_gate | 语义级偏差 | replan |
| recovery_loop | 同一任务 ≥3 次恢复 | replan |

**状态**：配置齐全，`MIMIR_AUTO_EVOLVE=1` 已启用，但生产环境尚未触发过 degeneration detection（无告警日志）。

---

## WM (World Model) — WorldModelPredictor

| 配置项 | 值 |
|--------|----|
| 来源 | Mimir 自研 Phase 0 (WB-B01) |
| 文件 | `agent/world_model_spike.py` (119 行) |
| 环境门控 | `MIMIR_WM_PREDICTOR`（默认 off） |

**支持 6 种意图预测：**
- recall → prior_session_context + memory_or_search
- code → source_files + repo_context
- debug → source_files + error_context + logs
- ops → runtime_status + service_logs
- chat → user_message
- general → user_message

**状态**：代码存在但 env 默认关闭（`MIMIR_WM_PREDICTOR` 未在 `.env` 中设置）。未在生产中启用。

---

## 快照结论

| 系统 | 状态 | 建议 |
|------|------|------|
| VoE/Degeneration Guard | ✅ 配置完整，生产中可用 | 无需改动 |
| WM Predictor | ⚠️ 代码就绪但未启用 | 如需启用：在 `.env` 加 `MIMIR_WM_PREDICTOR=1` 后重启 Gateway |
