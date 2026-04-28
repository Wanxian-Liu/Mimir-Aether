# Day 4: 上下文压缩 (context_compressor)

## 学习日期
2026-04-29

## 任务阶段
Week 1 - Day 4

---

## 阅读内容

### Hermes context_compressor.py (820行)
- 文件: `agent/context_compressor.py`
- 核心类: `ContextCompressor`
- 关键特性:
  - 5阶段压缩算法
  - 迭代摘要更新
  - 工具调用/结果对完整性检查
  - Token预算尾部保护
  - 失败冷却机制

### MimirAether context_compressor.py (840行)
- 文件: `agent/context_compressor.py`
- 核心类: `ContextCompressorV2` + `HermesStyleCompressor`
- 关键特性:
  - 继承ContextEngine抽象基类
  - LLM摘要 + 模板降级
  - 激进工具结果修剪
  - 按token预算尾部保护

---

## 关键发现

### 1. Hermes压缩算法

**5阶段压缩流程**:
```
Phase 1: 修剪旧工具结果（无LLM调用）
         ↓
Phase 2: 确定边界（保护头部+尾部）
         ↓
Phase 3: 生成结构化摘要（LLM调用）
         ↓
Phase 4: 组装压缩后的消息列表
         ↓
Phase 5: 清理孤立tool_call/result对
```

**关键常量**:
```python
SUMMARY_PREFIX = "[CONTEXT COMPACTION — REFERENCE ONLY]..."
_MIN_SUMMARY_TOKENS = 2000
_SUMMARY_RATIO = 0.20           # 摘要占压缩内容的比例
_SUMMARY_TOKENS_CEILING = 12_000
_SUMMARY_FAILURE_COOLDOWN_SECONDS = 600
```

### 2. MimirAether压缩算法

**与Hermes的差异**:

| 特性 | Hermes | MimirAether | 差异 |
|------|--------|-------------|------|
| 摘要生成 | LLM only | LLM + 模板降级 | MimirAether有降级方案 |
| 最小摘要token | 2000 | 500 | Hermes更保守 |
| 摘要token上限 | 12,000 | 8,000 | Hermes更大 |
| 尾部token预算 | 动态计算 | 固定4000 | Hermes动态 |
| 工具结果修剪 | ✅ | ✅(激进模式) | 类似 |
| 边界对齐 | ✅ | ✅ | 一致 |
| 迭代摘要 | ✅ | ❌ | Hermes有 |

### 3. 摘要模板对比

**Hermes结构化模板**:
```python
## Goal
## Constraints & Preferences
## Progress (Done/In Progress/Blocked)
## Key Decisions
## Resolved Questions
## Pending User Asks
## Relevant Files
## Remaining Work
## Critical Context
## Tools & Patterns
```

**MimirAether简化模板**:
```python
## 对话摘要
共N条消息（用户:X 助手:Y 工具:Z）
## 涉及内容
- 首条用户请求
- 工具输出
```

**差距**: ⚠️ Hermes的模板更结构化，MimirAether的更简单

### 4. 工具调用对完整性

**Hermes实现**:
```python
def _sanitize_tool_pairs(self, messages):
    """修复压缩后的孤立tool_call/result对"""
    # 1. 移除没有匹配call_id的工具结果
    # 2. 为没有结果的tool_call添加stub结果
```

**MimirAether**:
- ✅ 相同实现

### 5. 尾部保护算法

**Hermes**:
```python
def _find_tail_cut_by_tokens(self, messages, head_end, token_budget=None):
    """按token预算从后向前保护"""
    soft_ceiling = int(token_budget * 1.5)
    # 保留至少3条消息
    # 避免在tool组中间切割
```

**MimirAether**:
```python
def _find_tail_cut_by_tokens(self, messages, head_end):
    """固定tail_token_budget=4000"""
    # 与Hermes算法相同，但budget固定
```

**差距**: ⚠️ Hermes动态计算tail budget，MimirAether固定4000

### 6. 压缩触发条件

**Hermes**:
```python
def should_compress(self, prompt_tokens=None) -> bool:
    tokens = prompt_tokens or self.last_prompt_tokens
    return tokens >= self.threshold_tokens  # 50% of context
```

**MimirAether**:
```python
def should_compress(self, prompt_tokens=None) -> bool:
    tokens = prompt_tokens if prompt_tokens is not None else 0
    return tokens >= self.threshold_tokens  # 85% of context!
```

**差距**: ⚠️ Hermes用50%阈值，MimirAether用85%阈值

---

## 设计模式

### 1. 迭代摘要更新
```python
# Hermes: 保留前一次摘要，新内容合并
if self._previous_summary:
    prompt = f"PREVIOUS SUMMARY:\n{self._previous_summary}\n\nNEW TURNS:\n{content}"
    summary = _generate_summary(...)
    self._previous_summary = summary
```

### 2. 摘要失败冷却
```python
# Hermes: 摘要失败后冷却600秒
if summary_failed:
    self._summary_failure_cooldown_until = time.monotonic() + 600
    return None  # 静默降级
```

### 3. 压缩标记合并
```python
# Hermes: 避免角色连续冲突
last_head_role = messages[compress_start - 1].get("role")
first_tail_role = messages[compress_end].get("role")
# 选择不与head/tail冲突的角色
```

---

## MimirAether差距分析

### 关键差距

| 功能 | Hermes | MimirAether | 优先级 |
|------|--------|-------------|--------|
| 迭代摘要更新 | ✅ | ❌ | P1 |
| 动态tail budget | ✅ | ❌ | P1 |
| 压缩阈值50% | ✅ | ❌ | P1 |
| 结构化摘要模板 | ✅ | ❌ | P2 |
| focus_topic支持 | ✅ | ⚠️部分 | P2 |
| 摘要token上限12k | ✅ | ❌(8k) | P2 |

### 根因分析

MimirAether的ContextCompressorV2是**独立开发**的，不是直接复制Hermes。这导致:
1. 算法思路相似但参数不同
2. 摘要模板更简化
3. 缺少迭代摘要机制

---

## 问题与思考

### Q1: 为什么MimirAether用85%阈值而Hermes用50%?
A1: 可能原因:
- MimirAether假设使用更大的上下文窗口模型
- 更激进的阈值减少压缩频率
- 但可能导致上下文溢出风险增加

### Q2: MimirAether的LLM+模板降级方案是否合理?
A2: 合理。当LLM不可用时，模板摘要至少提供基本结构化信息，比完全丢失好。但模板摘要的信息密度远低于LLM摘要。

---

## 验证实验

### 实验1: 测试压缩触发
```python
# Hermes: 50%阈值
context_length = 128000  # GPT-4 Turbo
threshold = context_length * 0.50  # = 64000 tokens

# MimirAether: 85%阈值
context_length = 8000  # DeepSeek默认
threshold = context_length * 0.85  # = 6800 tokens
```

### 实验2: 测试迭代压缩
```python
# 运行两次压缩，检查_previous_summary是否被保留
compressor = ContextCompressor(...)
c1, r1 = compressor.compress(messages)
c2, r2 = compressor.compress(c1)
# Hermes: r2._previous_summary应该有值
# MimirAether: 检查是否被保留
```

---

## 风险标记

⚠️ **迭代摘要缺失** - MimirAether没有保留前一次摘要
⚠️ **压缩阈值过高** - 85%可能导致上下文溢出
⚠️ **Tail budget固定** - 不适应不同模型上下文大小

---

## 明日计划 (Day 5)

- [ ] 精读Hermes prompt_builder.py (1037行)
- [ ] 精读MimirAether prompt_builder.py
- [ ] 分析安全扫描机制
- [ ] 分析技能索引差异
