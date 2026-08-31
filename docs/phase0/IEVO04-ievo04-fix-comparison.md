# IEVO-04 议题六真根因修复 — 评测前后对比

## 根因

`scripts/run_evolution_eval.sh` L73/L84 用裸 `python3`（= `/usr/bin/python3`，无
torch/sentence-transformers）。`resolve_embedding_function()` 配置了
`MIMIR_EMBED_MODEL=/home/rayliu/models/bge-m3` 但加载失败时，旧代码**静默降级
hash(384维)**，而 collection 是 bge-m3（1024维）建的 → 维度不匹配 → 查询空结果 →
`semantic_hit_rate` 假 0.0（假退化）。

## 修复

1. `scripts/run_evolution_eval.sh`：裸 python3 → `${ROOT}/.venv/bin/python3`（PYTHON_BIN
   变量 + 缺失 fail-fast exit 2）；L73 benchmark + L84 compare 两处。
2. 全仓同型隐患扫描：碰 chroma/embed 的入口全部指向 .venv —
   - `scripts/backfill_chroma_sessions.py`（shebang → venv python，直连 chroma）
   - `scripts/start.sh`（gateway 入口）
   - `scripts/smoke_basics.sh`、`scripts/coverage_baseline.sh`、`scripts/run_evolution.sh`、
     `scripts/iq55_search_weekly.sh`（venv 优先，缺失回退 python3）
   - 已隔离无需改：`dream_memory_cron.sh`（已自行 source .venv）、`wm-kpi-verify.sh`/
     `mimir_health_check.sh`/`tool_quality_weekly.sh`（纯 JSON 处理，不碰 chroma/embed）
3. `tools/chroma_session_indexer.py` Loki 四条 fallback 加固：
   - 告警升级 **error 级**（原 logger.warning）
   - 写 **audit_log**（`~/.mimiraether/data/audit_log.jsonl`）
   - **连续失败熔断**（3 次 → circuit breaker raise）
   - **启动 fail-fast**（配置了 MIMIR_EMBED_MODEL 但解析失败 → raise，绝不静默降级 hash；
     修复 ValueError 陷阱——chromadb 缺 ST 时抛 ValueError 而非 ImportError）

## 实测对比

| 指标 | 修复前 (20260831T132835Z, 裸 python3) | 修复后 (20260831T161919Z, .venv) |
|------|--------------------------------------|----------------------------------|
| semantic_hit_rate | **0.0**（假数据） | **1.0**（真嵌入语义召回） |
| semantic_semantic_heavy_hit_rate | 0.0 | 1.0 |
| semantic_p50_ms | 9.1（秒回=没真跑） | 6012（真 bge-m3 推理） |
| 每条查询 semantic_hits | 全 0 | 3–13（均值 8.8） |

语义腿 20 查询全部真实命中（3~13 条/查询），compare vs baseline pass=true。

## fail-fast 验证（系统 python3 模拟旧场景）

```
embedding resolve FAILED (1/3): ... No module named 'torch'
embedding resolve FAILED (2/3): ... sentence-transformers/chromadb extras unavailable
FAIL-FAST RAISED (expected): MIMIR_EMBED_MODEL=... configured but unresolvable;
refusing hash fallback (dimension mismatch would fake semantic_hit_rate=0.0)
```
audit_log.jsonl 3 条 error 记录落盘确认。
