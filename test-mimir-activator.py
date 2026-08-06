#!/usr/bin/env python3
"""Mimir 激活桥——最小验证版（测试用，不修改任何现有代码）

功能：调用 Mimir 的 run_task 执行一条任务，验证 agent 能被触发
用法：python3 test-mimir-activator.py "任务内容"
"""
import sys, asyncio

async def main():
    task = sys.argv[1] if len(sys.argv) > 1 else "测试：请回复'激活桥工作正常'"
    print(f"🎯 调用 run_task: {task[:50]}...")

    from mimir_cli.task_runner import run_task
    result = await run_task(
        task=task,
        model="deepseek-v4-flash",
        max_iterations=5,
        verbose=False,
    )
    print(f"✅ run_task返回: {result}")
    return result

if __name__ == "__main__":
    asyncio.run(main())
