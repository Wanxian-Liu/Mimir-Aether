# Wave A · IQ 5.5 行为成绩单（2026-05-31）

> **拍板**：刘哥 §20.3 **IQ-RUBRIC-55** ✅ · 真源 [`MIMIR_IQ_EVOLUTION_DIRECTION.md`](../MIMIR_IQ_EVOLUTION_DIRECTION.md) §1.5

## 运维（宕机恢复）

| 项 | 结果 |
|----|------|
| 双实例根因 | 多次 `nohup`/`timeout` 残留 + `pkill -f gateway/run.py` 误伤/漏杀（bash 行含该字符串） |
| 修复 | 新增 `scripts/ensure_single_gateway.sh`（只杀 `python.*gateway/run.py`） |
| 自检 | `ps aux \| grep '[g]ateway/run.py'` 应 **仅 1 行** python |

## §1.5 合格检查表

| # | 检查项 | 合格线 | 结果 | 证据 |
|---|--------|--------|:----:|------|
| Q1 | Rubric 加权 | ≥5.5 或 exception | **4.9** | [`iq-scoring-rubric.md`](./iq-scoring-rubric.md) · **续 documented exception**（差 0.6） |
| Q2 | 历史类先 `session_search` | 3 场景 + 7d 基线 | **部分** | A04 rate=null · A05 audit 100% · **A09 飞书 3 场景 0P/1部分**（`iqevo-30` 2026-05-31）· A06 代码已合但 **log 仍 0× session_search** |
| Q3 | 进化可测 | `run_evolution_eval` 周常 | **PASS** | `~/.mimiraether/data/evolution_eval/memory-retrieval-latest.json` · compare **20260531T155907Z** 全 ok（LIKE 1.0 / FTS 0.5 / semantic 1.0） |
| Q4 | 工具质量可见 | top5 ok% 周常 | **PASS**（周常已跑） | **WA-A03**：top5 各 ok%=1.0、calls=1（低流量周）；高流量工具见 **WA-A00 手查** |
| Q5 | 反馈→行为 | JSONL + tune/1c | **待验证** | `data/feedback_collector.jsonl` **不存在** · 本机 `MIMIR_FEEDBACK_COLLECTOR` **未设置**（勿沿用旧报告 PASS） |
| Q6 | 学习/意图不造假 | #1/#8 诚实 | **PASS** | rubric 未虚标 IntentPredictor 全量上线 |
| Q7 | 纪律 | tier0≠智商 | **PASS** | tier0 645+2（OPS-L2 后） |

## 检索基准（Q3 附属 · 非行为）

```json
"like_hit_rate": 1.0,
"fts_hit_rate": 0.5,
"semantic_hit_rate": 1.0
```

路径：`$MIMIR_AETHER_HOME/data/evolution_eval/memory-retrieval-compare-20260531T155907Z.json`

## OPS-L2 / L2 预取

| 项 | 结果 |
|----|------|
| 代码路径 | session_key 对齐 · 本地 smoke **PASS**（正确 `agent:main:feishu:dm:oc_…`） |
| 生产 log | **无** `<retrieved-sessions>` 行（修复后尚无飞书真人复验） |

## WA-A00 刷新（2026-05-31 · Mimir 验收轨 / 真源核对）

| 项 | 刷新结论 |
|----|----------|
| Q1 | **4.9** 不变；Wave A 工程粒 A02～A10 未完成前 **不得** 抬分 |
| Q3 | **PASS** — `memory-retrieval-compare-20260531T155907Z.json` pass=true |
| Q4 | **PASS** — `tool_quality_weekly.sh` exit=0（top5 见上；calls 偏低） |
| Q5 | **待验证** — 反馈 JSONL 缺失；与 bridge「Wave 4 已开 collector」需 **gateway .env 对齐** 后再标 PASS |
| Q2 基线 | `session_search_baseline_7d.json` 已存在但 **0 会话** → 行为证据仍靠 A09 + 审计 |

**工具质量手查（非周常脚本）**：echo ~100% · read_file ~99.3% · terminal ~99.6% · search_files ~99.8% · crash_tool 0%（已知假阳性）。

## 结论

- **Wave A 成绩单**：离线进化 eval **达标**；**生产行为**（先搜再答、飞书 3 场景、反馈链）**未达标** → rubric **维持 4.9**，exception 续期合理。
- **Wave A 工程粒 A00～A12 [x]** · closeout [`wave-a-closeout.md`](./wave-a-closeout.md) · gateway **21329** 已载 WA-A06+A08 log。
- **可选复测**：飞书探针 ① + `grep session_search ~/.mimiraether/logs/agent.log`（验证 A06 行为，非抬分前提）。
- **下一战役**：**Wave B（WM Phase0）** 独立 PR · 或 **A06.1** 跨会话工具守卫。
