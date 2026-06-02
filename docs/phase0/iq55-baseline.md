# IQ-55 基线快照（2026-06-02）

> **勘误**：[`iq55-truth-refresh.md`](./iq55-truth-refresh.md) · **路线图**：[`../MIMIR_IQ55_ROADMAP.md`](../MIMIR_IQ55_ROADMAP.md)

## 代码 / 合入状态

| 项 | 值 |
|----|-----|
| `main` HEAD | `4f58b3d`（evolution ledger 写盘） |
| IQ-31～34 | 已合 `a0dc323` |
| §12 ENG-WF / §13 MW | 队列全 [x] |

## 指标（复测当日）

| 指标 | 值 | 证据 |
|------|:--:|------|
| IQ（上次 rubric） | **5.2** | `iq17-closeout.md`（文档待 IQ55-00 刷新） |
| search_first 原始违规率 | **90%** | `iqevo-31-search-first-audit.json` · 9 violations / 10 样本窗 |
| search_first filtered | **80%** | 同上 `filtered_violation_rate` |
| evolution_ledger | **4× planned** | `~/.mimiraether/data/evolution_ledger.json` · `outcome=planned` |
| brain_metrics 持久化 | **有** | `~/.mimiraether/data/ops/brain-metrics-latest.json` |
| tool P95 | **91s** 🚩 | health R3（待 IQ55-12 画像刷新） |

## 刘哥生产 env（本日已执行）

| 变量 | 状态 |
|------|------|
| `MIMIR_WM_PREDICTOR=1` | ✅ 已写入 `~/.mimiraether/.env` |
| `MIMIR_NUDGE_INTERVAL=3` | ✅ 已写入 |
| `MIMIR_PARALLEL_TOOLS=1` | ⏸ 未开（建议观察 WM 3～7 天后再开） |
| `MIMIR_AUTO_ANALYSIS=1` | ✅ 既有 |
| `MIMIR_AUTO_EVOLVE=1` | ✅ 既有 |
| Gateway | ✅ `ensure_single_gateway.sh` · health=ok · pid 15137 |

## 5.5 缺口（尚不能宣称达标）

- [ ] P0.1 搜索 filtered ≤40%
- [ ] P0.2 ledger ≥1 `applied`
- [ ] P1.1 intent 7d 生产命中（brain_metrics）

## 下一粒（Mimir）

```bash
./scripts/mimir_iq55_run_next.sh --dry-run
# 预期：IQ55-00 或 IQ55-02（IQ55-01 已 [x]）
```
