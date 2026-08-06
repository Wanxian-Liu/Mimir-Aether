#!/usr/bin/env python3
"""用正确的env加载方式测试run_task（模拟gateway行为）"""
import os, asyncio

from mimir_cli.env_loader import load_hermes_dotenv
load_hermes_dotenv(
    hermes_home=os.path.expanduser("~/.mimiraether"),
    project_env=os.path.join(os.path.dirname(__file__), ".env"),
)
k = os.environ.get("DEEPSEEK_API_KEY", "")
print(f"load_hermes_dotenv后 key: 前缀{k[:5]} 长度{len(k)} 尾4位{k[-4:]}")

async def main():
    from mimir_cli.task_runner import run_task
    await run_task(task="回复：Mimir验证成功", model="deepseek-v4-flash", max_iterations=3, verbose=False)

if __name__ == "__main__":
    asyncio.run(main())
