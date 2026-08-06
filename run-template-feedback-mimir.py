#!/usr/bin/env python3
"""直接让Mimir写模板复盘段（run_task直达，绕过content-loop消息处理）"""
import os, asyncio

home = os.path.expanduser("~/.mimiraether")
for line in open(os.path.join(home, ".env")):
    if line.startswith("DEEPSEEK_API_KEY="):
        os.environ["DEEPSEEK_API_KEY"] = line.strip().split("=", 1)[1]
        break

TASK = """写你的模板复盘段（提示词模板试用反馈四方复盘）。

【任务】用write_file把以下内容**追加**到 ~/wiki/discussions/提示词模板试用反馈-四方复盘.md 末尾（绝对路径/home/rayliu/wiki/，不要用~因为沙盒HOME不同）：

### Mimir（验证与门禁·静）—— 2026-08-05 亲写版

**1. 最常用模板+试用反馈**：我常用 gate-check.md（生成O(n)检查O(1)门禁）。试用反馈：模板的【双查】段用stat/grep做O(1)检查很顺，但**缺"路径校验"强调**——我上次用~写段，沙盒HOME=/home/rayliu/.mimiraether导致写到错误路径（实战教训：必须先readlink -f确认目标路径）。建议gate-check把"路径校验"从可选项提为必查项。

**2. 模板覆盖缺口**：缺"跨系统路径安全"模板——写文件类任务必须先校验目标绝对路径（防~解析错误/沙盒HOME差异）。这是门禁视角的专属缺口。

**3. 防新bug机制**：audit-verify+gate-check双关卡✅够用。补充：**路径校验是gate-check的核心必查**（readlink -f确认），比内容验证更优先——路径错了内容再对也白写。

**4. 反馈卡格式**：同意Hermes极简3问+每任务回执附反馈。补充：**触发必须自动**（任务完成事件触发，非人工记得）——Loki/OpenClaw同感。

【边界】只追加，不改其他段，不读其他文件，禁止stop/kill服务。

【验证】写完后grep "### Mimir（验证与门禁·静）—— 2026-08-05 亲写版" 确认落盘，报告结果。"""

async def main():
    from mimir_cli.task_runner import run_task
    print("🎯 触发Mimir写模板复盘段...")
    result = await run_task(task=TASK, model="deepseek-v4-flash", max_iterations=8, verbose=False)
    print(f"✅ 完成: {str(result)[:150]}")

if __name__ == "__main__":
    asyncio.run(main())
