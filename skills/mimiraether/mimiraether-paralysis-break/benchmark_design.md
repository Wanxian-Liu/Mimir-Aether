# 上下文压缩基准测试方案

> 生成时间: 2026-04-30 | 测试对象: `mimiraether-context-compressor`

---

## 1. 测试目标

测量 MimirAether 上下文压缩器的三个核心维度：

| 维度 | 指标 | 目标值 |
|------|------|--------|
| 压缩效率 | 压缩率 (Compression Ratio) | ≥ 50% 减少 |
| 信息保真 | 关键信息保留率 (Retention Rate) | ≥ 85% |
| 处理性能 | 压缩耗时 (Latency) | < 5秒 |

---

## 2. 测试数据

### 2.1 数据来源

从 `sessions.db`（**`$MIMIR_AETHER_HOME/data/sessions/...`** 或你配置的会话 DB 路径；勿写死机器路径）选取：

| 会话 ID | Token 总数 | 输入 Token | 用途 |
|----------|-----------|-----------|------|
| `demo_session` | 33,000 | 26,000 | 主测试用例（高token密度） |
| `test_insights_001` | 16,500 | 13,000 | 中等规模验证 |

### 2.2 数据提取方法

```python
# 从 session_events 表提取消息序列
SELECT event_type, event_data 
FROM session_events 
WHERE session_id = ? 
ORDER BY id ASC
```

每个 event 的 `event_data` JSON 中包含原始消息内容（如 `tool_result`, `user_message`, `assistant_message` 等）。

### 2.3 测试数据分层

为覆盖不同场景，构造三组测试数据：

- **A组 - 纯对话**: 仅提取 user/assistant 文本消息
- **B组 - 含工具输出**: 保留 tool_call + tool_result（模拟真实场景）
- **C组 - 混合**: 完整会话记录（未过滤）

每组从 `demo_session` 中抽取不同规模的子集：
- Small: ~5,000 tokens
- Medium: ~15,000 tokens
- Large: ~25,000 tokens

---

## 3. 测量指标定义

### 3.1 压缩率 (Compression Ratio, CR)

```
CR = 1 - (compressed_tokens / original_tokens)
```

- CR = 0.0: 无压缩
- CR = 0.5: 压缩到原来一半
- CR = 0.8: 压缩到原来 20%
- 目标: CR ≥ 0.50

### 3.2 关键信息保留率 (Information Retention Rate, IRR)

**第一步 - 定义"关键信息"**：从原始消息中自动提取以下类别的实体：

| 类别 | 提取规则 | 示例 |
|------|---------|------|
| FILE | 文件路径引用 | `$MIMIR_AETHER_HOME/...` 形态示例（常用默认 `$HOME/.mimiraether`）；勿硬编码本机 home |
| DECISION | 用户明确的选择/决定 | "用 PostgreSQL" |
| ERROR | 错误消息 | traceback, error code |
| CONFIG | 配置参数值 | `threshold_percent: 0.50` |
| QUESTION | 用户提出的待解决问题 | "How do I...?" |
| ACTION | 已执行的关键操作 | "created a new branch" |

**第二步 - 检查保留**：

```
IRR = |压缩后仍存在的事实| / |原始关键事实总数|
```

每个事实检查方式：
- 精确匹配: 字符串包含检查（对路径/配置值）
- 语义匹配: LLM 判断摘要是否传达了相同信息（对决策/问题）

**目标: IRR ≥ 0.85**

### 3.3 摘要质量评分 (Summary Quality Score, SQS)

5 分制人工/LLM 评估（对结构化摘要模板的各字段打分）：

| 模板字段 | 权重 | 评分标准 |
|----------|------|---------|
| Goal | 15% | 是否准确捕捉用户目标 |
| Constraints & Preferences | 15% | 是否保留约束和偏好 |
| Progress (Done/In Progress/Blocked) | 25% | 完成/进行中/阻塞项是否完整 |
| Key Decisions | 15% | 技术决策及原因是否保留 |
| Critical Context | 15% | 关键配置/错误/值是否记录 |
| Remaining Work | 10% | 剩余工作是否正确 |
| Resolved Questions | 5% | 已解决问题是否记录 |

**目标: SQS ≥ 3.5 / 5.0**

### 3.4 处理性能

```
Latency = 压缩函数执行时间（毫秒）
```

分两阶段测量：
- 阶段1（工具输出修剪）: < 100ms
- 阶段2（LLM摘要生成）: < 5000ms（取决于模型）

---

## 4. 测试实施步骤

### 步骤 1: 准备测试数据 (~2 分钟)

```bash
# 运行数据提取脚本
python tests/benchmarks/prepare_test_data.py \
  --db-path "$MIMIR_AETHER_HOME/data/sessions/sessions.db" \
  --session-id demo_session \
  --output-dir tests/benchmarks/data/
```

产出：
- `data/group_a_small.json`
- `data/group_a_medium.json`
- `data/group_a_large.json`
- (B组、C组同理)

### 步骤 2: 运行压缩器 (~3 分钟)

```bash
python tests/benchmarks/run_compression_benchmark.py \
  --data-dir tests/benchmarks/data/ \
  --compressor context_compressor \
  --output-dir tests/benchmarks/results/
```

对每组数据的每次压缩记录：
- 原始 token 数
- 压缩后 token 数
- 各阶段耗时
- 生成的摘要文本

### 步骤 3: 计算指标 (~2 分钟)

```bash
python tests/benchmarks/calculate_metrics.py \
  --results-dir tests/benchmarks/results/ \
  --output tests/benchmarks/metrics.json
```

自动计算 CR、IRR、Latency，SQS 留待人工/LLM 评估。

### 步骤 4: 生成报告 (~1 分钟)

```bash
python tests/benchmarks/generate_report.py \
  --metrics tests/benchmarks/metrics.json \
  --output tests/benchmarks/report.md
```

---

## 5. 预期产出格式

### 5.1 指标汇总表 (metrics.json)

```json
{
  "benchmark_metadata": {
    "date": "2026-04-30",
    "compressor_version": "v2",
    "data_source": "demo_session (33K tokens)"
  },
  "results": [
    {
      "group": "A",
      "size": "medium",
      "original_tokens": 15234,
      "compressed_tokens": 4521,
      "compression_ratio": 0.70,
      "retention_rate": 0.88,
      "phase1_latency_ms": 45,
      "phase2_latency_ms": 2100,
      "summary_quality_score": null
    }
  ],
  "aggregates": {
    "mean_compression_ratio": 0.68,
    "mean_retention_rate": 0.86,
    "mean_total_latency_ms": 2340,
    "pass_rate": "85% (11/13 tests pass targets)"
  }
}
```

### 5.2 详细报告 (report.md)

```
# Context Compressor Benchmark Report
## Summary
- Overall Score: 82/100
- Status: ✅ PASS (all targets met)

## Compression Efficiency
- Mean CR: 0.68 (target: ≥0.50) ✅
- Best case: 0.82 (large pure-conversation)
- Worst case: 0.45 (small mixed-content)

## Information Fidelity
- Mean IRR: 0.86 (target: ≥0.85) ✅
- Category breakdown:
  - FILE: 95% retention
  - DECISION: 78% retention ⚠️ (below target)
  - ERROR: 91% retention
  - CONFIG: 88% retention
  - QUESTION: 82% retention
  - ACTION: 84% retention

## Performance
- Mean latency: 2.34s (target: <5s) ✅
- Phase 1 (pruning): 45ms avg
- Phase 2 (LLM summary): 2.1s avg

## Failures & Edge Cases
- Small sessions (<3000 tokens) show CR <0.50 — overhead dominates
- DECISION retention low when decisions span multiple messages
- One timeout on 25K-token mixed-content group

## Recommendations
1. Improve multi-message decision tracking in summary template
2. Skip compression for sessions <3000 tokens (cost > benefit)
3. Add retry logic for LLM timeout on very large inputs
```

---

## 6. 成功标准

| 标准 | 阈值 | 必须 |
|------|------|------|
| 所有测试执行完成 | 100% | 是 |
| 平均压缩率 | ≥ 0.50 | 是 |
| 平均保留率 | ≥ 0.85 | 是 |
| 平均延迟 | < 5s | 是 |
| 无数据丢失 | 0 丢失 | 是 |
| SQS（需人工评估） | ≥ 3.5/5 | 否（nice-to-have） |

---

## 7. 附录: 为什么这些指标

### 7.1 压缩率 vs 保留率的权衡

高压缩率容易（丢掉所有内容），高保留率也容易（不做压缩）。真正的难度在于 **同时达到两者**。

因此核心评价公式：

```
Effectiveness Score = CR × IRR
```

只有在压缩和保留都好的情况下得分才高。目标: ES ≥ 0.43 (0.50 × 0.85)

### 7.2 分层测试的意义

- **A组（纯对话）**: 最佳场景，测试压缩器在理想条件下的性能上限
- **B组（含工具输出）**: 常见场景，测试大段工具输出的修剪效果
- **C组（混合）**: 真实场景，端到端测试

### 7.3 与 Hermes 原版的对齐

本方案指标与 Hermes Agent `context_compressor.py` 的设计参数直接对齐：
- `threshold_percent: 0.50` → 压缩率目标 ≥0.50
- `summary_target_ratio: 0.20` → 摘要应为压缩内容的 20%
- `protect_first_n: 3` → HEAD 保护验证
- `protect_last_n: 20` → TAIL 保护验证
