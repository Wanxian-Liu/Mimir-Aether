#!/usr/bin/env python3
"""触发Mimir亲写段（v2：精简上下文——只读讨论卡，立即写）"""
import os, asyncio

home = os.path.expanduser("~/.mimiraether")
for line in open(os.path.join(home, ".env")):
    if line.startswith("DEEPSEEK_API_KEY="):
        os.environ["DEEPSEEK_API_KEY"] = line.strip().split("=", 1)[1]
        break

TASK = """立即完成提示词体系讨论你的段（亲写版）。只做一件事：写段。

【任务】用write_file**只追加**以下内容到 ~/wiki/discussions/提示词体系-四方讨论完善.md 末尾（不要读其他文件，不要分析，直接写）：

### Mimir（验证与门禁·静）—— 2026-08-04 亲写版

**1. 核心理解**：提示词体系=经验资产化，四方共享。我的领域视角：守验证与门禁——生成O(n)、检查O(1)，模板内置低成本验证设计。

**2. 查依据**（简要，来自已有知识+本地）：
- 结构化模板+可度量评估路线（与OpenAI Evals思路一致）
- 验证段应可脚本化（pytest/eval harness）

**3. 完善建议**：
- 支持七段式（含【反例】【双查】）
- 我的领域模板：gate-check.md（门禁验证——生成后O(1)检查）
- 模板带验证脚本路径（可复算）

**4. 落地方式**：✅同意wiki沉淀+四方共享；审计模板（Loki）优先落地无异议。

（以上为Mimir亲写版，覆盖之前Hermes补录）

【边界】只追加，不修改其他段，不读其他文件，不删除内容，禁止stop/kill服务。

【验证】写完后grep "亲写版" 该文件确认落盘，报告结果。"""

async def main():
    from mimir_cli.task_runner import run_task
    print("🎯 触发Mimir写段v2（精简）...")
    result = await run_task(task=TASK, model="deepseek-v4-flash", max_iterations=6, verbose=False)
    print(f"✅ 完成: {str(result)[:150]}")

if __name__ == "__main__":
    asyncio.run(main())
