
================================================================================
MimirAether 自我迭代总结报告
================================================================================

迭代日期: 2026-04-28
基于: Hermes Agent 架构研究

--------------------------------------------------------------------------------
1. 多层次错误恢复机制 (MultiLevelRecovery)
--------------------------------------------------------------------------------

学习自Hermes的4层恢复策略:

Level 1: RETRY (重试)
  - 指数退避 + Jitter
  - 默认最大重试3次
  - base_delay=1.0s, max_delay=30.0s

Level 2: DEGRADE (降级)
  - 降级模型参数
  - 可配置降级配置列表
  - temperature: 0.3 → 0.1

Level 3: COMPRESS (压缩)
  - 触发上下文压缩
  - 标记context_probed状态
  - 避免过度压缩

Level 4: TRUNCATE (截断)
  - 强制截断历史
  - 保留最近N条消息
  - 最后保护机制

统计追踪:
  - total_errors: 总错误数
  - retry_success: 重试成功数
  - degrade_success: 降级成功数
  - compress_success: 压缩触发数
  - truncate_success: 截断触发数
  - unrecoverable: 无法恢复数

--------------------------------------------------------------------------------
2. 增强迭代预算控制 (EnhancedIterationBudget)
--------------------------------------------------------------------------------

继承自Hermes IterationBudget，新增功能:

预算分级警告:
  - SAFE: > 30% 剩余
  - WARNING: 10% - 30% 剩余
  - CRITICAL: < 10% 剩余
  - EXHAUSTED: 0% 剩余

工具分类:
  - FREE_TOOLS: execute_code, bash 等不消耗预算
  - EXPENSIVE_TOOLS: browser, web_search 等每次消耗2次

工具预算分配:
  - set_tool_budget(tool_name, budget)
  - consume_tool_budget(tool_name)
  - 精细化控制特定工具使用

历史追踪:
  - IterationRecord: 每次迭代的详细记录
  - action, tool_name, success, duration, tokens
  - 最大保留1000条历史

--------------------------------------------------------------------------------
3. Hermes风格上下文压缩 (HermesStyleCompressor)
--------------------------------------------------------------------------------

继承自ContextCompressorV2，新增Hermes对齐功能:

1. 工具结果修剪 (无LLM调用)
   - prune_tool_results_aggressive()
   - 保留最近N个工具结果

2. 按Token保护尾部
   - protect_tail_by_tokens()
   - 使用token预算而非固定消息数

3. 迭代摘要
   - _iterative_summary: 支持多次压缩更新
   - _previous_summary: 保存上次摘要

4. 上下文探测
   - mark_context_probed()
   - is_context_probed()
   - 从错误恢复后标记

5. 压缩判断
   - should_trigger_compression()
   - 包含reserve空间计算
   - 冷却期检查

--------------------------------------------------------------------------------
4. 集成到MimirAetherAgent
--------------------------------------------------------------------------------

在 core_loop.py 中新增:

辅助方法:
  - get_budget_warning(): 获取当前预算警告
  - get_recovery_stats(): 获取恢复统计
  - check_and_warn_budget(): 检查并警告预算
  - handle_error_with_recovery(): 使用恢复处理错误
  - _recovery_error_handler(): 恢复错误处理器
  - _truncate_history(): 截断对话历史

初始化:
  - EnhancedIterationBudget(max_total=max_iterations)
  - MultiLevelRecovery(max_retries=3)
  - HermesStyleCompressor(model=model)

--------------------------------------------------------------------------------
5. 文件变更
--------------------------------------------------------------------------------

新增文件:
  - agent/recovery.py: 多层次错误恢复模块
  - agent/iteration_budget.py: 增强迭代预算控制

修改文件:
  - agent/context_compressor.py: 添加HermesStyleCompressor
  - agent/core_loop.py: 集成新模块

--------------------------------------------------------------------------------
6. 向后兼容
--------------------------------------------------------------------------------

保留以下接口以兼容旧代码:
  - from .iteration_budget import IterationBudget
  - from .context_compressor import ContextCompressor

================================================================================
