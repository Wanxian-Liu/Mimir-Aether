#!/usr/bin/env python3
"""P1-3.5 pass3 — 补溯 p1_3_35_fix 漏掉的卡（正文含真实本地路径引用但被标 unknown）。

规则（同 P1-3.3/3.4 pass3）：
- 只改 frontmatter 的 source 字段，不动正文与其他字段
- 候选 = 正文明确引用的真实本地路径 / wiki 内关联卡（test -f / test -d 验证）
- 排除自引用、排除通用文件名
- 每张处理后立即 read back 验证

候选依据来自 p1_3_35_pass3_ctx.py 正文上下文提取（逐卡人工判定）。
用法: python3 scripts/p1_3_35_pass3.py
"""
import json, os, re

WIKI = "/home/rayliu/wiki"

TARGETS = {
    "discussions/Mimir-P0执行报告-自我审计.md": [
        "/home/rayliu/.mimiraether/data/p0_after_bgem3.json",
    ],
    "discussions/MimirGateway身份矛盾调查.md": [
        "/home/rayliu/.mimiraether/SOUL.md",
    ],
    "discussions/Mimir不落盘-架构根因深挖.md": [
        "/home/rayliu/src/MimirAether/agent/agent_loop.py",
    ],
    "discussions/Mimir体检-C1效果验证.md": [
        "/home/rayliu/src/MimirAether/mimir-content-loop-v2.py",
    ],
    "discussions/Mimir原子整改清单-四方逐项投票.md": [
        "/home/rayliu/src/MimirAether/agent/agent_loop.py",
    ],
    "discussions/Mimir双循环架构-根因与修复.md": [
        "/home/rayliu/src/MimirAether/agent/agent_loop.py",
    ],
    "discussions/Mimir可靠性专项-四方会诊.md": [
        "/home/rayliu/.mimiraether/data/trajectories/2026-08-04/4d7f4db20d8af08a.jsonl",
    ],
    "discussions/Mimir向Hermes学习-实验讨论.md": [
        "/home/rayliu/.hermes/SOUL.md",
    ],
    "discussions/Mimir学Hermes-第一学习点选定.md": [
        "/home/rayliu/.hermes/hermes-agent/agent/conversation_loop.py",
    ],
    "discussions/Mimir学习成果审视-四方会议.md": [
        "/home/rayliu/wiki/discussions/Mimir学Hermes-第一学习点选定.md",
    ],
    "discussions/Mimir整改B组-四方讨论.md": [
        "/home/rayliu/src/MimirAether/agent/prompt_builder.py",
    ],
    "discussions/Mimir整改C组-机制修复四方讨论.md": [
        "/home/rayliu/src/MimirAether/mimir-content-loop-v2.py",
    ],
    "discussions/Mimir整改二次讨论-执行前验证.md": [
        "/home/rayliu/src/MimirAether/agent/skill_commands.py",
    ],
    "discussions/Mimir整改执行记录.md": [
        "/home/rayliu/archive/mimir-empty-shell-20260806/",
    ],
    "discussions/Mimir核心体检-1循环执行.md": [
        "/home/rayliu/src/MimirAether/agent/agent_loop.py",
    ],
}

GENERIC = {"AGENTS.md", "SOUL.md", "MEMORY.md", "SKILL.md", "README.md", "LEARNINGS.md", "CLAUDE.md", "USER.md", "index.md"}


def to_wiki_rel(p):
    if p.startswith(WIKI + "/"):
        return p[len(WIKI) + 1:]
    return p


def fix_one(rel, candidates):
    path = os.path.join(WIKI, rel)
    if not os.path.exists(path):
        return {"file": rel, "action": "missing", "source": None}
    text = open(path, encoding="utf-8").read()
    if not text.startswith("---"):
        return {"file": rel, "action": "no-frontmatter", "source": None}
    lines = text.splitlines()
    end = None
    for i in range(1, min(len(lines), 60)):
        if lines[i].strip() == "---":
            end = i
            break
    if end is None:
        return {"file": rel, "action": "no-frontmatter", "source": None}
    fm_lines = lines[1:end]
    body = "\n".join(lines[end + 1:])

    src = None
    for c in candidates:
        c2 = c.replace("~", "/home/rayliu")
        if os.path.exists(c2):
            base = os.path.basename(c2.rstrip("/"))
            if "/" not in c2.replace("\\", "/") and base in GENERIC:
                continue
            if c2.rstrip("/") == path.rstrip("/"):
                continue  # 自引用
            src = to_wiki_rel(c2)
            break
    if not src:
        return {"file": rel, "action": "no-valid-candidate", "source": None}

    new_fm = []
    replaced = False
    for l in fm_lines:
        if re.match(r"^source\s*:", l) and not replaced:
            new_fm.append(f'source: "{src}"')
            replaced = True
        else:
            new_fm.append(l)
    if not replaced:
        new_fm.append(f'source: "{src}"')
    new_text = "---\n" + "\n".join(new_fm) + "\n---\n" + body
    open(path, "w", encoding="utf-8").write(new_text)

    verify = open(path, encoding="utf-8").read()
    ok = f'source: "{src}"' in verify.split("---", 2)[1] if verify.startswith("---") else False
    return {"file": rel, "action": "fixed", "source": src, "verified": ok}


def main():
    results = []
    for rel, cands in TARGETS.items():
        r = fix_one(rel, cands)
        results.append(r)
        print(f"{r['file']} | {r['action']} | {r.get('source')} | verified={r.get('verified')}")
    json.dump(results, open("/tmp/p1_3_35_pass3_results.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    from collections import Counter
    print("\n统计:", dict(Counter(r["action"] for r in results)))
    print("DONE")


if __name__ == "__main__":
    main()
