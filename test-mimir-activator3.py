#!/usr/bin/env python3
"""Mimir 激活桥测试 v3——强制注入key并追踪来源"""
import sys, os, asyncio

# 强制从用户.env注入真key
home = os.path.expanduser("~/.mimiraether")
for line in open(os.path.join(home, ".env")):
    if line.startswith("DEEPSEEK_API_KEY="):
        os.environ["DEEPSEEK_API_KEY"] = line.strip().split("=", 1)[1]
        break
print(f"注入后os.environ key: 前缀{os.environ['DEEPSEEK_API_KEY'][:5]} 尾4位{os.environ['DEEPSEEK_API_KEY'][-4:]}")

# 看provider_registry解析结果
from agent.provider_registry import resolve_api_key_provider_credentials
creds = resolve_api_key_provider_credentials("deepseek")
print(f"registry解析: key前缀={str(creds.get('api_key'))[:5]} 来源={creds.get('source')}")

async def main():
    task = sys.argv[1] if len(sys.argv) > 1 else "测试"
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
