#!/usr/bin/env python3
"""强制Mimir落盘本次找bug任务段（run_task直达，明确写卡路径）"""
import os, asyncio

home = os.path.expanduser("~/.mimiraether")
for line in open(os.path.join(home, ".env")):
    if line.startswith("DEEPSEEK_API_KEY="):
        os.environ["DEEPSEEK_API_KEY"] = line.strip().split("=", 1)[1]
        break

TASK = """立即把你在"四方协作行为找bug"任务中的回答写入讨论卡。

【任务】用write_file（绝对路径！禁止/tmp）把这些内容写入 /home/rayliu/wiki/discussions/四方协作行为找bug-落盘纪律验证.md 的末尾（追加，用"### Mimir"标题）：

### Mimir（知识/代码专家）—— 2026-08-05 亲写版

**1. 审查语义搜索系统发现的bug**：
[你刚才审查发现的bug——如incremental_index缩进问题/frontmatter问题，带文件:行号]

**2. 自检我的落盘纪律**：
[如实：最近几次任务我几次落盘/几次没落盘]

**3. 改进建议**：
[你的建议，如写卡路径规范化]

【边界】只追加到指定文件，不改其他段，禁止stop/kill服务，禁止写/tmp。
【验证】写完后grep "### Mimir" 该文件确认落盘+报告结果。"""

async def main():
    from mimir_cli.task_runner import run_task
    print("🎯 强制Mimir落盘找bug段...")
    result = await run_task(task=TASK, model="deepseek-v4-flash", max_iterations=8, verbose=False)
    print(f"✅ 完成: {str(result)[:150]}")

if __name__ == "__main__":
    asyncio.run(main())
