# MimirAether 架构分析

## 核心组件 (2026-04-24 更新)

### 1. Agent 核心
| 组件 | 文件 | 行数 | 状态 |
|------|------|------|------|
| core_loop | agent/core_loop.py | 2163 | ✅ 完成 |
| auxiliary_client | agent/auxiliary_client.py | 2614 | ✅ 完成 |
| anthropic_adapter | agent/anthropic_adapter.py | 1411 | ✅ 完成 |

### 2. 上下文管理
| 组件 | 文件 | 功能 |
|------|------|------|
| context_compressor | agent/context_compressor.py | 上下文压缩 |
| context_references | agent/context_references.py | @引用展开 |
| prompt_builder | agent/prompt_builder.py | System Prompt构建 |

### 3. 凭证与限流
| 组件 | 文件 | 功能 |
|------|------|------|
| credential_pool | agent/credential_pool.py | 多API密钥轮换 |
| rate_limit_tracker | agent/rate_limit_tracker.py | 限速追踪 |

### 4. 工具系统
- **28+ 内置工具**: 文件操作、代码执行、技能管理等
- **74+ 可复用技能**: github、mlops、software-development等
- **FTS5 跨会话搜索**: ✅ 已实现
- **MCP工具**: browser_tool, mcp_tool, delegate_tool等

### 5. Hook系统
- **Hermes 插件Hook**: ✅ 已添加
- **Session 恢复**: ✅ 已实现

## 迭代记录

### 2026-04-25
- 清理 .env.backup 备份文件
- integration_core.py:443 TODO 评估: 会话过滤功能暂时搁置（pass占位符，功能优先级低）
- plugin.py:340 TODO 评估: 插件专属配置系统需对接记忆殿堂配置层，中期规划

### 2026-04-24
- 清理.bak备份文件 (3个文件)
- core_loop.py 优化

### 2026-04-23
- 从Hermes学习新增1500+行代码
- OAuth/Token兼容函数
- 上下文引用处理增强
- Insights引擎集成

## 1:1 对齐状态

| P0组件 | Hermess行数 | MimirAether行数 | 状态 |
|--------|-------------|-----------------|------|
| auxiliary_client | - | 2614 | ✅ 完成 |
| anthropic_adapter | - | 1411 | ✅ 完成 |
| AIAgent core | - | 2163 | ✅ 完成 |
