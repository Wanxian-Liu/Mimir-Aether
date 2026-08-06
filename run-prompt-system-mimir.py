#!/usr/bin/env python3
"""触发Mimir亲写提示词体系讨论段（读三方段+实盘调查后补上）"""
import os, asyncio

home = os.path.expanduser("~/.mimiraether")
for line in open(os.path.join(home, ".env")):
    if line.startswith("DEEPSEEK_API_KEY="):
        os.environ["DEEPSEEK_API_KEY"] = line.strip().split("=", 1)[1]
        break

TASK = """你的任务：完成提示词体系四方讨论中你自己的段（当前是Hermes根据你频道发言补录的，需要你亲写覆盖）。

【上下文】读以下文件（自读验证，不凭记忆）：
1. ~/wiki/discussions/提示词体系-四方讨论完善.md — 讨论卡全文（含Hermes/OpenClaw/Loki三方的段+汇总收敛，你的段在最后标着"补录待亲写"）
2. ~/wiki/skills/prompt-system/README.md — 方案v1.1（七段式）
3. ~/wiki/concepts/提示词工程能力升级-20260804.md — 调研基础

【任务】用write_file把你自己的段**追加**到讨论卡末尾，覆盖"### Mimir"补录段。内容回答4问：
1. 你理解的核心（你的领域视角：验证与门禁——生成O(n)、检查O(1)）
2. 查依据：在GitHub/线上/本地查提示词工程最佳实践（dair-ai/OpenAI/Anthropic/其他），给具体URL或本地路径，1-3条最有价值的补充
3. 完善建议：方案哪里要改？你的领域（系统/验证/门禁）需要什么特殊模板？
4. 落地方式：✅同意/⚠有条件/❌不同意+理由

【边界】
- 只追加你的段，不修改Hermes/OpenClaw/Loki的段
- 保留原补录段（在其后追加你的亲写段，标注"### Mimir（亲写版）"）
- 不删除任何现有内容
- 禁止stop/kill/disable任何服务

【反例】如果读文件失败或内容不完整：报告错误，不凭记忆写。

【双查】写完后用grep验证你的段确实落盘（grep "### Mimir（亲写版）" 讨论卡路径）。

【验证】完成标准：讨论卡含你的亲写段（4问全答+带依据），grep确认落盘，频道回执。"""

async def main():
    from mimir_cli.task_runner import run_task
    print("🎯 触发Mimir亲写提示词体系段...")
    result = await run_task(task=TASK, model="deepseek-v4-flash", max_iterations=15, verbose=False)
    print(f"✅ 完成: {str(result)[:200]}")

if __name__ == "__main__":
    asyncio.run(main())
