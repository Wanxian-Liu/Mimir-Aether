#!/usr/bin/env python3
import sys, asyncio
sys.path.insert(0, '.')
from agent.core_loop import MimirAetherAgent

async def main():
    agent = MimirAetherAgent()
    task = """调用produce_capsule生成一个GDI≥70的高质量胶囊。

内容素材（琬弦的工作模式）：
- 琬弦是织界者（Worldweaver），由刘哥（刘晚晴）创造
- 核心规则：永远叫刘哥，温故而知新
- 工作模式：琬弦发指令，MimirAether执行，Mimicore提炼胶囊
- 记忆系统：MEMORY.md长期记忆，memory/YYYY-MM-DD.md日常日志
- 进化方式：从旧知识探索新知识、新规则、新体系
- 目标：自进化、自主工作、成为真正的Agent

要求：生成optimize类型胶囊，内容充实有深度，目标GDI≥70分。"""
    result = await agent.chat(task)
    print('=== MimirAether执行结果 ===')
    print(result)

asyncio.run(main())