# IQ-Q5 · FeedbackCollector 生产验证（2026-06-01）

> **轨**：IQ 5.5 Phase2 · Track Q5  
> **代码**：[`agent/feedback_collector.py`](../../agent/feedback_collector.py) · Wave 4 IQ-EVO-16

## 验收

| 项 | 结果 | 证据 |
|----|:----:|------|
| `MIMIR_FEEDBACK_COLLECTOR=1` | **PASS** | `$MIMIR_AETHER_HOME/.env` |
| `data/feedback_events.jsonl` 存在且有行 | **PASS** | `~/.mimiraether/data/feedback_events.jsonl` · **3989** 行（2026-06-01 抽检） |
| 末行 `event_type` | **PASS** | `analysis_artifact`（抽检） |
| Gateway 重启 | **未本轮** | collector 已在运行；下轮 env 变更时再 `ensure_single_gateway.sh` |

## 与 Wave A §1.5

- **Q5**：由「待验证」→ **PASS**（生产 JSONL + env 对齐 bridge Wave 4 叙述）
- 不单独抬 rubric 总分；见 [`iq-55-phase2-closeout.md`](./iq-55-phase2-closeout.md)

## 刻意未做

- `MIMIR_AUTO_TUNER=1`（Wave 5 范围）
- 本轨无 Python 代码变更

## 复验命令

```bash
grep '^MIMIR_FEEDBACK_COLLECTOR=' "$MIMIR_AETHER_HOME/.env"
wc -l "$MIMIR_AETHER_HOME/data/feedback_events.jsonl"
tail -1 "$MIMIR_AETHER_HOME/data/feedback_events.jsonl" | python3 -m json.tool
```
