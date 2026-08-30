#!/usr/bin/env python3
"""Mimir顺畅性验证：清噪音后跑一次写卡任务"""
import os, asyncio

home = os.path.expanduser("~/.mimiraether")
for line in open(os.path.join(home, ".env")):
    if line.startswith("DEEPSEEK_API_KEY="):
        os.environ["DEEPSEEK_API_KEY"] = line.strip().split("=", 1)[1]
        break

TASK = """【顺畅性验证】把以下内容写入 " + os.environ.get("MIMIR_WIKI_ROOT", os.path.expanduser("~/wiki")) + "/concepts/Mimir顺畅性验证-20260805.md（绝对路径）：

# Mimir顺畅性验证
收件箱噪音清理后，Mimir应顺畅落盘。
本次任务验证：写卡完成。

【边界】只写这个文件，禁止读其他文件。
【验证】写完后terminal stat确认。"""

async def main():
    from mimir_cli.task_runner import run_task
    print("🎯 顺畅性验证...")
    result = await run_task(task=TASK, model="deepseek-v4-flash", max_iterations=6, verbose=False)
    print(f"✅ 完成: {str(result)[:120]}")

if __name__ == "__main__":
    asyncio.run(main())
