#!/usr/bin/env python3
"""提取 15 张卡正文中真实存在路径的上下文行（前后 1 行），辅助 pass3 补溯人工判定。"""
import os, re

WIKI = "/home/rayliu/wiki"

CARDS = {
    "discussions/Mimir-P0执行报告-自我审计.md": ["p0_after_bgem3.json", "p0_baseline_hash.json", "scripts/p0/"],
    "discussions/MimirGateway身份矛盾调查.md": ["backups/mimir/"],
    "discussions/Mimir不落盘-架构根因深挖.md": ["agent_loop.py", "evolution_log.md", "feedback_events.jsonl", "testing-reality-checker.md", "MEMORY.md"],
    "discussions/Mimir体检-C1效果验证.md": ["testing-reality-checker.md", "trajectories", "AGENTS.md", "SOUL.md"],
    "discussions/Mimir原子整改清单-四方逐项投票.md": ["engineering-software-architect.md", "testing-reality-checker.md", "agent_loop.py", "core_loop.py"],
    "discussions/Mimir双循环架构-根因与修复.md": ["src/MimirAether/agent/"],
    "discussions/Mimir可靠性专项-四方会诊.md": ["trajectories/2026-08-04/1410436f16210658.jsonl", "trajectories/2026-08-04/4d7f4db20d8af08a.jsonl", "mimir-content-loop-v2.py", "提示词模板试用反馈-四方复盘.md", "audit-verify.md"],
    "discussions/Mimir向Hermes学习-实验讨论.md": ["testing-reality-checker.md", ".hermes/", "MEMORY.md"],
    "discussions/Mimir学Hermes-第一学习点选定.md": ["conversation_loop.py", "claw-superpowers", "agent_loop.py"],
    "discussions/Mimir学习成果审视-四方会议.md": ["Mimir学Hermes-第一学习点选定.md", "mimir-content-loop-v2.py"],
    "discussions/Mimir整改B组-四方讨论.md": ["agent_loop.py", "core_loop.py", "prompt_builder.py", "fix_cross_session.py"],
    "discussions/Mimir整改C组-机制修复四方讨论.md": ["delegate_subagent.py", "subagent.py", "pi_crew_bridge.py", "mimir-content-loop-v2.py", "skill_commands.py"],
    "discussions/Mimir整改二次讨论-执行前验证.md": ["display.py", "skill_commands.py", "refactor_backup"],
    "discussions/Mimir整改执行记录.md": ["projects/MimirAether", "src/MimirAether", ".openclaw/skills/"],
    "discussions/Mimir核心体检-1循环执行.md": ["agent_loop.py", ".hermes/hermes-agent/agent/"],
}

for rel, needles in CARDS.items():
    path = os.path.join(WIKI, rel)
    lines = open(path, encoding="utf-8").read().splitlines()
    print(f"\n########## {rel} ##########")
    for i, l in enumerate(lines):
        for n in needles:
            if n in l:
                lo = max(0, i - 1)
                hi = min(len(lines), i + 2)
                ctx = " | ".join(x.strip()[:110] for x in lines[lo:hi])
                print(f"  L{i+1}: {ctx}")
                break
