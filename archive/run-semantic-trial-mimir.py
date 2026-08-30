#!/usr/bin/env python3
"""触发Mimir写语义搜索试用段（run_task直达）"""
import os, asyncio

home = os.path.expanduser("~/.mimiraether")
for line in open(os.path.join(home, ".env")):
    if line.startswith("DEEPSEEK_API_KEY="):
        os.environ["DEEPSEEK_API_KEY"] = line.strip().split("=", 1)[1]
        break

TASK = """写你的语义搜索试用段（语义搜索四方试用-找bug）。

【任务】先用semantic_search实测你领域的查询（用venv python: /home/rayliu/.hermes/hermes-agent/.venv/bin/python3），然后把这些内容**追加**到 /home/rayliu/wiki/discussions/语义搜索四方试用-找bug.md 末尾（**绝对路径，不用~**）：

### Mimir（知识/代码专家）—— 2026-08-05 亲写版

**实测**：[记录你的查询+返回结果]
**评估**：[相关吗？相似度合理吗？]
**发现的bug**：[你观察到的，如索引滞后/召回问题]
**建议**：[怎么改进]

【边界】只追加，不改其他段，禁止stop/kill服务。
【验证】写完后grep "### Mimir" 确认落盘，报告结果。"""

async def main():
    from mimir_cli.task_runner import run_task
    print("🎯 触发Mimir写试用段...")
    result = await run_task(task=TASK, model="deepseek-v4-flash", max_iterations=10, verbose=False)
    print(f"✅ 完成: {str(result)[:150]}")

if __name__ == "__main__":
    asyncio.run(main())
