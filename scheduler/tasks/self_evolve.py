#!/usr/bin/env python3
"""
自进化任务
执行MimirAether的自进化过程，分析记忆殿堂的自进化模块，参照Hermes的调度机制，
给出如何提升自动化修复能力的具体建议。
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

def run_self_evolve():
    """执行自进化"""
    print("执行MimirAether自进化...")
    try:
        from agent.core_loop import MimirAetherAgent
        import asyncio
        
        async def evolve():
            agent = MimirAetherAgent(model="kimi-k2.5", max_iterations=2)
            result = await agent.run_conversation(
                "分析记忆殿堂的自进化模块，参照Hermes的调度机制，"
                "给出如何提升自动化修复能力的具体建议。"
            )
            return result
        
        return asyncio.run(evolve())
    
    except Exception as e:
        print(f"自进化失败: {e}")
        return f"error: {e}"

if __name__ == "__main__":
    result = run_self_evolve()
    print(f"自进化结果: {str(result)[:500] if result else 'None'}")