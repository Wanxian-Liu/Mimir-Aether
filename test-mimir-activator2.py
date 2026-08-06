#!/usr/bin/env python3
"""Mimir 激活桥测试 v2——模拟gateway的env加载方式"""
import sys, os, asyncio

# 先加载.env（模拟gateway行为）
from dotenv import load_dotenv
home = os.path.expanduser("~/.mimiraether")
load_dotenv(os.path.join(home, ".env"))
print(f"DEEPSEEK_API_KEY长度: {len(os.environ.get('DEEPSEEK_API_KEY',''))}")

async def main():
    task = sys.argv[1] if len(sys.argv) > 1 else "测试：请回复'激活桥工作正常'"
    print(f"🎯 调用 run_task: {task[:40]}...")

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
