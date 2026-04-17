#!/usr/bin/env python3
import sys, asyncio
sys.path.insert(0, '.')
from agent.core_loop import MimirAetherAgent

async def main():
    agent = MimirAetherAgent()
    task = """请调用produce_capsule生成一个关于"织界者琬弦与MimirAether协作流程"的高质量胶囊。

内容要点：
- 琬弦（指挥官）：只发指令给MimirAether，不直接执行
- MimirAether（执行者）：接收琬弦指令，调用Mimicore完成工作
- Mimicore（提炼者）：将知识整理成胶囊，GDI≥0.6发布

请生成optimize类型胶囊，内容充实有深度。"""
    result = await agent.chat(task)
    print('=== MimirAether执行结果 ===')
    print(result)

asyncio.run(main())