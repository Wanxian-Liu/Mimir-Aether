# Memory 检索引擎基准测试（方法论）

**日期**：2026-05-21  
**来源**：EV-A03（琬弦架构方案方向三 — Memory 语义化升级 P2）

> ⚠️ 当前无法运行基准测试（需要真实 memory SQLite DB + 20 条 query），本文档建立方法论和基线框架。

## 测试设计

### 20 条 Query 样本（待运行）

| # | Query | 类型 | 期望 Semantic 胜出？ |
|---|-------|------|:--:|
| 1 | "刘哥项目的架构方案" | 语义/模糊 | ✅ |
| 2 | "persistent.json 截断事件" | 精确/关键字 | ❌ |
| 3 | "Gateway 崩溃怎么恢复" | 语义/问答 | ✅ |
| 4 | "DeepSeek 的 tool call 格式问题" | 精确/技术术语 | ❌ |
| 5 | "IR 事故的根因" | 语义/回忆 | ✅ |
| ... | (共 20 条，覆盖精确/语义/中英混合/时间限定) | | |

### 评估指标

| 指标 | 公式 | LIKE 预期 | Semantic 目标 |
|------|------|:--:|:--:|
| **Precision** | TP/(TP+FP) | 0.90 (精确匹配高) | ≥0.85 |
| **Recall** | TP/(TP+FN) | 0.40 (模糊匹配低) | ≥0.80 |
| **F1** | 2×P×R/(P+R) | 0.55 | ≥0.82 |
| **Latency (P50)** | 50th percentile | <10ms (LIKE on small DB) | <50ms (chromadb 本地) |
| **Latency (P99)** | 99th percentile | <50ms | <200ms |

### 当前 LIKE 检索的已知局限

| 局限 | 示例 | Semantic 解决 |
|------|------|:--:|
| 无法匹配同义词 | "崩溃" ≠ "crash" | ✅ embedding 相似 |
| 中文分词差异 | "架构问题" ≠ "系统架构的问题" | ✅ |
| 跨语言匹配 | "memory leak" ≠ "内存泄漏" | ✅ (bge 中英双语) |
| 无相关度排序 | LIKE 返回全或无 | ✅ cosine similarity |

## 运行方法（待刘哥或 Cursor 执行）

```bash
cd ~/src/MimirAether
python -c "
from agent.memory_benchmark import run_benchmark
results = run_benchmark(n_queries=20)
print(f'LIKE   F1={results[\"like\"][\"f1\"]:.2f} P50={results[\"like\"][\"p50_ms\"]:.0f}ms')
print(f'Semantic F1={results[\"semantic\"][\"f1\"]:.2f} P50={results[\"semantic\"][\"p50_ms\"]:.0f}ms')
print(f'Delta F1={results[\"delta_f1\"]:+.2f}')
"
```

## 结论

基准测试框架已建立，但需要真实运行环境。等方向三启动时先运行本基准，用数据（而非假设）验证语义检索的收益。
