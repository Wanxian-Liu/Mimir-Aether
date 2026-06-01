# IQ-17 刘哥拍板登记（真源）

> **状态**：刘哥 **2026-05-19** 已全部拍板（「我都拍板」）。  
> **模板**：[`MIMIR_IQ17_EXECUTION_PLAN.md`](../MIMIR_IQ17_EXECUTION_PLAN.md) §3

| 键 | 选项 | 刘哥决定 | 日期 | 执行粒 |
|----|------|----------|------|--------|
| D16 | 确认 / 暂缓 | **确认** | 2026-05-19 | IQ-04 [x] |
| A | 开 / 暂缓 | **开** | 2026-05-19 | IQ-10 |
| WM-Q1 | 开 / 暂缓 | **开** | 2026-05-19 | IQ-11 |
| WM-Q2 | 自动 / 每步问我 | **每步问我** | 2026-05-19 | IQ-12 |
| WM-Q3 | 批准 / 暂缓 | **批准** | 2026-05-19 | IQ-31 |
| C | 只.env / 改默认 / 暂缓 | **只保持 .env=1，不改代码默认** | 2026-05-19 | IQ-13 |
| D | 增强MVP / 暂缓 / Phase2 | **增强 MVP** | 2026-05-19 | IQ-32～34 |
| E | 仅设计 / 暂缓 | **仅设计** | 2026-05-19 | IQ-40 |
| F | 仅设计 / 暂缓 | **仅设计** | 2026-05-19 | IQ-41 |
| **WM-Q5** | 做 B5 LLM WM / **不做** | **不做（保持现状）** | 2026-05-19 | 见 [`wm-b5-llm-predictor-deferred.md`](./wm-b5-llm-predictor-deferred.md) |

**运维提醒（刘哥 shell，非飞书 turn）**

- Gateway 重启后 SELF-11 / PREREQ 才生效：`MIMIR_AETHER_HOME=~/.mimiraether ./scripts/ensure_single_gateway.sh`
- WM B1：在 `~/.mimiraether/.env` 增加 `MIMIR_WM_VOE_LEARNING=1` 后重启 gateway
