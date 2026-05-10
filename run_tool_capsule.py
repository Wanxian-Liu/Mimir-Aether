#!/usr/bin/env python3
"""通过mimircore_tool生成胶囊"""

import os
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(_REPO_ROOT))

from tools.mimircore_tool import produce_capsule

# 胶囊内容：MimirAether与Hermes对标
input_text = """
MimirAether与Hermes核心能力对标报告

1. 核心能力对齐状态

1.1 消息处理
- Hermes: 支持流式输出、多provider路由、错误恢复
- MimirAether: 需要完整实现流式输出、Provider路由、错误恢复
- 差距: 核心功能缺失，功能对齐率约40%

1.2 会话管理
- Hermes: sessions_send(17%成功率), sessions_spawn(95%成功率)
- MimirAether: 需要实现sessions_spawn/sessions_send封装
- 差距: 缺少稳定的消息传递机制

1.3 工具生态
- Hermes: 完整的工具注册、发现、执行体系
- MimirAether: 需要完善工具生态，包括builtin tools整合
- 差距: 工具生态不完整

1.4 记忆系统
- Hermes: 记忆殿堂、checkpoint恢复机制
- MimirAether: 需要继承和改进记忆系统
- 差距: 需要确保记忆跨会话连续性

2. 工具Fitness数据（Foundry ADAS 2026-04-23）
- sessions_spawn: 高Fitness, ~95%成功率
- sessions_send: 低Fitness, ~17%成功率（避免使用）
- canvas: 0% Fitness（完全不可用，需替代方案）

3. 关键发现
- sindri角色模式：plan()→subtasks→spawn()→yield()
- sessions_send成功率过低，不应作为主要通信方式
- subagent是可靠的执行单元

4. 改进方向
- 优先实现sessions_spawn封装
- 避免依赖sessions_send
- 使用browser替代canvas
- 建立稳定的Provider路由机制

5. 核心原则
- 真正有用，而不是表演有用
- 跳过"好问题！"和"很高兴帮你！"
- 行动比话语更有力
"""

result = produce_capsule(
    input_text=input_text,
    capsule_type="auto",
    auto_publish=True
)

print(result)
