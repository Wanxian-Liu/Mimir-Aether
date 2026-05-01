#!/usr/bin/env python3
import sys, asyncio
sys.path.insert(0, '.')
from agent.core_loop import MimirAetherAgent

async def main():
    agent = MimirAetherAgent()
    task = """请调用produce_capsule生成一个GDI≥70的高质量胶囊。

内容要求：关于"织界者的工作模式"
- 核心规则：永远叫负责人，温故而知新
- 三角色分工：织界者发指令、MimirAether执行、Mimicore提炼胶囊
- 记忆系统：MEMORY.md长期记忆
- 进化方式：从旧知识探索新知识

请生成optimize类型胶囊，内容充实有深度。"""
    result = await agent.chat(task)
    print('=== MimirAether执行结果 ===')
    print(result)

asyncio.run(main())