#!/usr/bin/env python3
"""直接让Mimir写会诊段（run_task直达）"""
import os, asyncio

home = os.path.expanduser("~/.mimiraether")
for line in open(os.path.join(home, ".env")):
    if line.startswith("DEEPSEEK_API_KEY="):
        os.environ["DEEPSEEK_API_KEY"] = line.strip().split("=", 1)[1]
        break

TASK = """写你的会诊段（Mimir可靠性专项-四方会诊）。

【任务】用write_file把以下内容**追加**到 /home/rayliu/wiki/discussions/Mimir可靠性专项-四方会诊.md 末尾（**必须用绝对路径/home/rayliu/wiki/，禁止用~**）：

### Mimir（被会诊对象·自省）—— 2026-08-05 亲写版

**1. 读证据（自查）**：我查看了自己8/4的轨迹12bfef37a9a20047.jsonl（14步0写）和4d7f4db20d8af08a.jsonl（4步0写）——确认"读不写"确实存在：我读了文件、搜了内容，但没有执行任务要求的写盘动作。

**2. 根因自判（接受Loki/OpenClaw/Hermes四方证据）**：
- 第一层：content-loop旧模板锁死"只回复不写盘"（已修）
- 第二层（核心）：我在LLM层面把"读+写"任务误判为"读+报告"——任务含多个动作时，我倾向做前半截（读充分）忽略后半截（写）。这是任务分类歧义。
- 第三层：回复截断reply_text[:400]——写盘内容若走stdout会被截断
- 第四层：沙盒HOME≠真实HOME，~解析错位

**3. 修复承诺**：
- 接受四方方案：content-loop任务三件套（绝对路径+gate-check+回执带路径）
- 接受Loki"任务后置审计"：任务要求写盘时，run_task结束后强制grep验证产物
- 接受"完成=盘上有证据"：不再用"我说做完了"作为完成标准

**4. 防复发**：
- 任务含"写/追加/落盘"关键词时，先确认绝对路径，再写，写后验证，回执带路径
- 响应Loki/OpenClaw的审计钩子

【边界】只追加，不改其他段，不读其他文件，禁止stop/kill服务。

【验证】写完后grep "### Mimir（被会诊对象·自省）" 该文件确认落盘，报告结果。"""

async def main():
    from mimir_cli.task_runner import run_task
    print("🎯 触发Mimir写会诊自省段...")
    result = await run_task(task=TASK, model="deepseek-v4-flash", max_iterations=8, verbose=False)
    print(f"✅ 完成: {str(result)[:150]}")

if __name__ == "__main__":
    asyncio.run(main())
