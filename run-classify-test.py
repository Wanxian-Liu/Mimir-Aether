#!/usr/bin/env python3
"""Mimir修复v3/v4后验证：跑一个含'讨论'字样的任务（检验分类修复）"""
import os, asyncio

home = os.path.expanduser("~/.mimiraether")
for line in open(os.path.join(home, ".env")):
    if line.startswith("DEEPSEEK_API_KEY="):
        os.environ["DEEPSEEK_API_KEY"] = line.strip().split("=", 1)[1]
        break

# 任务名含"讨论"——检验分类修复（修复前会误判成讨论消息不落盘）
TASK = """【四方讨论待办验证】写一个验证文件。

【任务】用write_file把内容写入 /home/rayliu/wiki/concepts/Mimir分类修复验证-20260805.md（绝对路径）：
# Mimir分类修复验证
任务名含"讨论"字样——修复v4后应正确按任务处理（不误判为讨论消息）。
本次验证：写卡完成。

【边界】只写这个文件，禁止读其他文件。
【验证】写完后terminal stat确认。"""

async def main():
    from mimir_cli.task_runner import run_task
    print("🎯 分类修复验证（任务名含'讨论'）...")
    result = await run_task(task=TASK, model="deepseek-v4-flash", max_iterations=6, verbose=False)
    print(f"✅ 完成: {str(result)[:120]}")

if __name__ == "__main__":
    asyncio.run(main())
