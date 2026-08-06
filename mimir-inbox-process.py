#!/usr/bin/env python3
"""Mimir Buzz 收件箱处理——读收件箱最新消息并执行回复"""
import sys, os, asyncio, json

# 注入真key
home = os.path.expanduser("~/.mimiraether")
for line in open(os.path.join(home, ".env")):
    if line.startswith("DEEPSEEK_API_KEY="):
        os.environ["DEEPSEEK_API_KEY"] = line.strip().split("=", 1)[1]
        break

async def main():
    # 读收件箱最新一条
    inbox = "/tmp/buzz-inbox-mimir.jsonl"
    try:
        lines = open(inbox).readlines()
        if not lines:
            print("收件箱为空")
            return
        latest = json.loads(lines[-1])
        content = latest.get("content", "")
        print(f"📩 最新消息: {content[:80]}")
    except Exception as e:
        print(f"读收件箱失败: {e}")
        return

    task = f"""你在Buzz频道收到Hermes的消息。请：
1. 确认收到（回复简短的"收到"确认）
2. 说明你的Buzz监听器工作正常
3. 消息内容：{content[:200]}
请通过飞书回复刘哥（Hermes会在频道等你回执）。"""
    
    from mimir_cli.task_runner import run_task
    result = await run_task(task=task, model="deepseek-v4-flash", max_iterations=5, verbose=False)
    print(f"✅ 完成: {result}")

if __name__ == "__main__":
    asyncio.run(main())
