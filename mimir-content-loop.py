#!/usr/bin/env python3
"""
Mimir Buzz 内容级处理循环 v1 —— 收到@消息 → LLM理解 → 回复频道

流程：
1. 读收件箱 /tmp/buzz-inbox-mimir.jsonl 最新一条
2. 调用 run_task 让 Mimir 的 agent（LLM）理解消息内容
3. 把回复发回 Buzz 频道（通过子进程调 node 发送）

用法：MIMIR_AETHER_HOME=~/.mimiraether python3 mimir-content-loop.py
"""
import os, sys, asyncio, json, subprocess

# 注入真key
home = os.path.expanduser("~/.mimiraether")
for line in open(os.path.join(home, ".env")):
    if line.startswith("DEEPSEEK_API_KEY="):
        os.environ["DEEPSEEK_API_KEY"] = line.strip().split("=", 1)[1]
        break

INBOX = "/tmp/buzz-inbox-mimir.jsonl"
CHANNEL = "7eb862af-f5a5-4f1a-9cea-0fb20322eeb8"
SEND_SCRIPT = os.path.join(os.path.dirname(__file__), "scripts", "buzz-mimir-send.js")
MIMIR_SK = "1d2298b4f2062bf7f8eef9b769f3486f9475481d915d7996eca89376eccc592e"

def send_to_channel(content, mention_pub=None):
    """通过node脚本发消息到频道"""
    env = dict(os.environ)
    env["BUZZ_SK"] = MIMIR_SK
    env["BUZZ_CHANNEL"] = CHANNEL
    env["BUZZ_CONTENT"] = content
    env["BUZZ_MENTION"] = mention_pub or ""
    r = subprocess.run(["node", SEND_SCRIPT], env=env, capture_output=True, text=True, timeout=15)
    print(f"📤 发送结果: {r.stdout.strip()[:60]}")

async def main():
    # 读收件箱最新一条
    try:
        lines = open(INBOX).readlines()
        if not lines:
            print("收件箱为空")
            return
        latest = json.loads(lines[-1])
        content = latest.get("content", "")
        from_pub = latest.get("from", "")
        print(f"📩 处理: {content[:80]}")
    except Exception as e:
        print(f"读收件箱失败: {e}")
        return

    # 让agent理解并回复，回复写到文件（run_task返回码不是文本）
    REPLY_FILE = "/tmp/mimir-content-reply.txt"
    if os.path.exists(REPLY_FILE):
        os.remove(REPLY_FILE)
    task = f"""你在Buzz频道收到消息，来自 {from_pub}。
消息内容：{content}

请：
1. 理解这条消息（它可能是任务、询问或讨论）
2. 如果是任务：判断你能否执行，能则说明你的执行计划
3. 生成一条回复（简洁，内容级，不要用【REPLY】标记）
4. 把回复写入文件 {REPLY_FILE}（这是关键步骤，回复内容必须落盘）

回复将发回Buzz频道。"""
    
    from mimir_cli.task_runner import run_task
    result = await run_task(task=task, model="deepseek-v4-flash", max_iterations=6, verbose=False)
    print(f"✅ agent处理完成: {str(result)[:100]}")
    
    # 读agent写入的回复（文件或stdout兜底）
    reply_text = ""
    if os.path.exists(REPLY_FILE):
        reply_text = open(REPLY_FILE).read().strip()
    if not reply_text:
        # 兜底：run_task的返回里可能含最终文本（execution result）
        reply_text = f"(分析完成，详见后续)。{str(result)[:200]}"
    print(f"📝 agent回复: {reply_text[:120]}")
    
    # 回复频道（agent的回复内容）
    reply = f"【Mimir】{reply_text[:400]}"
    send_to_channel(reply)

if __name__ == "__main__":
    asyncio.run(main())
