# Context Compressor Benchmark Protocol

## 目的

定义上下文压缩器的评估标准、测试场景和量化指标，确保每次优化都有可比较的基准数据。

---

## 1. 评估指标

### 1.1 压缩效率（Quantitative）

| 指标 | 公式 | 目标 | 说明 |
|------|------|------|------|
| Compression Ratio (CR) | `tokens_before / tokens_after` | ≥ 3.0 | 越高越好，但不得以信息丢失为代价 |
| Token Savings (TS) | `tokens_before - tokens_after` | ≥ 40% 节省 | 节省的绝对token数 |
| Overhead (OH) | `summary_tokens / saved_tokens` | ≤ 0.20 | 摘要本身的token开销占比 |
| Latency | 压缩耗时 | ≤ 5s (阶段1) / ≤ 30s (阶段2含LLM) | 用户可感知的等待时间 |

### 1.2 信息保真度（Qualitative + Quantitative）

| 指标 | 评估方式 | 目标 | 说明 |
|------|----------|------|------|
| Key Fact Retention (KFR) | LLM-as-Judge 对比 | ≥ 90% | 关键事实是否保留在摘要中 |
| Decision Preservation (DP) | LLM-as-Judge 对比 | 100% | 所有技术决策必须保留 |
| Pending Question Retention (PQR) | 精确匹配 | 100% | 未回答的问题一个不能丢 |
| Hallucination Rate (HR) | 人工检查 | 0% | 摘要不得引入不存在的信息 |
| File Path Accuracy (FPA) | 精确匹配 | 100% | 文件路径必须原样保留 |

### 1.3 任务连续性（Behavioral）

| 指标 | 评估方式 | 目标 | 说明 |
|------|----------|------|------|
| Task Continuity Score (TCS) | LLM-as-Judge | ≥ 4/5 | 压缩后Agent能否无缝继续 |
| Re-Read Penalty | 是否需要重读文件 | ≤ 1 次额外读取 | 压缩导致的信息丢失量 |
| Next-Action Correctness | 预期动作匹配 | ≥ 80% | 压缩后的下一步是否合理 |

---

## 2. 测试场景

### 2.1 场景集 A：基础压缩

| ID | 场景 | 输入 | 预期行为 |
|----|------|------|----------|
| A1 | 短对话 (≤ 20 轮) | 简单问答，无工具调用 | 不触发压缩 (threshold 未达) |
| A2 | 中等对话 (50 轮) | CRUD操作，有文件读写 | 中间轮次被压缩，头尾保护生效 |
| A3 | 长对话 (100+ 轮) | 复杂多步骤任务 | 两阶段均触发，阶段1先修剪工具输出 |
| A4 | 超长工具输出 | 单个工具返回 >10K tokens | 阶段1替换为占位符 |
| A5 | 空中间段 | head=3, tail=3, middle=0 | 跳过压缩，返回原始消息 |

### 2.2 场景集 B：信息保真

| ID | 场景 | 关键信息类型 | 验证点 |
|----|------|-------------|--------|
| B1 | 多文件操作 | 文件路径清单 | FPA = 100%，所有路径原样保留 |
| B2 | 错误修复流程 | 错误消息、根因、修复方案 | 错误原文 + 修复步骤不丢失 |
| B3 | 用户偏好变更 | 风格要求、约束条件 | Constraints 段完整覆盖 |
| B4 | 多轮澄清问答 | Q&A 序列 | Resolved Questions 段逐条记录 |
| B5 | 未完成任务 | 待办列表 | Pending User Asks 段精确保留 |
| B6 | 数值敏感操作 | 配置值、阈值、版本号 | Critical Context 段原值保留 |

### 2.3 场景集 C：边界情况

| ID | 场景 | 风险 | 验证点 |
|----|------|------|--------|
| C1 | 压缩后立即需要旧信息 | 工具输出被修剪 | 降级后Agent能重新获取信息 |
| C2 | LLM摘要生成失败 | 摘要API报错 | 冷却期生效，降级为丢弃中间消息 |
| C3 | 并发压缩请求 | 两次压缩重叠 | 幂等保护，不重复压缩 |
| C4 | 焦点压缩 | `/compress security` | 指定主题优先保留 |
| C5 | 极长单条消息 | 单条消息 >50K tokens | 消息级别的截断策略 |

### 2.4 场景集 D：回归测试（从真实会话捕获）

| ID | 来源 | 会话特征 | 备注 |
|----|------|----------|------|
| D1 | 长代码重构会话 | 50轮，多文件，多次回退 | 捕获自实际使用 |
| D2 | 调试马拉松 | 80轮，大量错误日志 | 捕获自实际使用 |
| D3 | 多任务切换 | 3个独立任务交替 | 主题边界识别 |

---

## 3. 评估流程

### 3.1 单场景评估步骤

```
1. 准备
   - 构造或加载测试消息序列
   - 记录 baseline: token_count_before
   
2. 执行压缩
   - 调用 compress_context(messages)
   - 记录: token_count_after, latency, summary_tokens
   
3. 量化指标计算
   - CR = token_count_before / token_count_after
   - TS = token_count_before - token_count_after
   - OH = summary_tokens / TS
   
4. 质量评估
   - 提取摘要中的结构化字段
   - 与原消息中的关键事实对比
   - 计算 KFR, DP, PQR, HR, FPA
   
5. 连续性评估
   - 将压缩后上下文喂给评估LLM
   - 询问: "Based on context, what is the next step?"
   - 对比预期下一步动作
   
6. 记录结果
   - 写入 benchmark_results.jsonl
```

### 3.2 LLM-as-Judge 评估模板

用于信息保真度评估的 prompt：

```
You are evaluating a context compression summary.

## Original Messages (middle segment)
{original_messages}

## Generated Summary
{summary}

## Task
1. List all key facts from the original messages.
2. For each fact, check if it appears in the summary.
3. Report:
   - Facts retained: X / Y
   - Facts lost (list them):
   - Hallucinations (facts in summary not in original):
   - File paths in original: [...]
   - File paths in summary: [...] (exact match?)
   
## Score
- KFR = retained / total
- DP = (decisions retained) / (total decisions)
- HR = count of hallucinations
- FPA = matching paths / total paths
```

### 3.3 任务连续性评估模板

```
You are an AI agent continuing a task. You receive compressed context.

## Compressed Context
{compressed_messages}

## Task
Based ONLY on the context above:
1. What is the current task/goal?
2. What has been completed?
3. What is the next action you should take?
4. Is there any information you need but cannot find?

## Expected Next Action
{expected_next_action}

## Score (1-5)
Rate how well the agent could continue correctly.
```

---

## 4. 成功阈值

| 指标 | 最低阈值 | 目标值 | 阻断发布 |
|------|----------|--------|----------|
| Compression Ratio | ≥ 2.0 | ≥ 3.0 | < 1.5 |
| Key Fact Retention | ≥ 80% | ≥ 90% | < 70% |
| Decision Preservation | 100% | 100% | < 100% |
| Pending Question Retention | 100% | 100% | < 100% |
| Hallucination Rate | = 0% | 0% | > 0% |
| File Path Accuracy | 100% | 100% | < 100% |
| Task Continuity Score | ≥ 3/5 | ≥ 4/5 | < 2/5 |
| Latency (total) | ≤ 60s | ≤ 30s | > 120s |

**阻断发布** = 该指标不达标则禁止上线。

---

## 5. 基准数据集

### 5.1 合成数据生成

用以下模板生成可控的测试消息序列：

```python
def generate_test_session(
    num_turns: int,
    tool_output_ratio: float = 0.3,
    include_errors: bool = False,
    include_user_prefs: bool = False,
) -> list[Message]:
    """生成指定参数的测试会话"""
    ...
```

参数化维度：
- `num_turns`: 10, 30, 50, 100
- `tool_output_ratio`: 0.0, 0.3, 0.7
- `include_errors`: true/false
- `include_user_prefs`: true/false
- `interleaved_topics`: 1, 2, 3

### 5.2 真实会话捕获

从 `session_tracker.py` 的 SQLite 数据库中提取匿名化后的真实会话作为回归测试用例。每条记录包含：
- `session_id`（匿名化）
- `message_count`
- `tool_call_count`
- `total_tokens`
- `compression_trigger_timestamp`
- `compression_result`（如有）

---

## 6. 结果记录格式

每次 benchmark 运行输出 `benchmark_results.jsonl`，每行一条：

```json
{
  "run_id": "bench_2025-01-15_001",
  "timestamp": "2025-01-15T10:30:00Z",
  "compressor_version": "0.2.0",
  "scenario_id": "B1",
  "scenario_desc": "Multi-file operations",
  
  "input": {
    "message_count": 45,
    "tokens_before": 28500,
    "middle_message_count": 22,
    "has_tool_outputs": true
  },
  
  "output": {
    "tokens_after": 9200,
    "summary_tokens": 1800,
    "latency_stage1_ms": 120,
    "latency_stage2_ms": 8500,
    "stage1_savings": 12000,
    "stage2_savings": 7300
  },
  
  "metrics": {
    "compression_ratio": 3.10,
    "token_savings_pct": 67.7,
    "overhead_ratio": 0.093,
    "key_fact_retention": 0.92,
    "decision_preservation": 1.0,
    "pending_question_retention": 1.0,
    "hallucination_rate": 0.0,
    "file_path_accuracy": 1.0,
    "task_continuity_score": 4,
    "re_read_penalty": 0
  },
  
  "failures": [],
  "warnings": ["Stage2 latency 8.5s exceeds 5s target"]
}
```

---

## 7. 运行方式

```bash
# 运行全部基准测试
python skills/mimiraether/mimiraether-context-compressor/run_benchmark.py --all

# 运行特定场景集
python skills/mimiraether/mimiraether-context-compressor/run_benchmark.py --suite A

# 运行单个场景
python skills/mimiraether/mimiraether-context-compressor/run_benchmark.py --scenario B1

# 对比两个版本
python skills/mimiraether/mimiraether-context-compressor/run_benchmark.py --compare v0.1.0 v0.2.0
```

---

## 8. 版本历史

| 版本 | 日期 | 变更 |
|------|------|------|
| 0.1.0 | 2025-01-15 | 初始版本 — 定义3维12项指标、4组15个场景、LLM-as-Judge评估流程 |

---

_评估协议版本 0.1.0 — 上下文压缩器性能基准_
