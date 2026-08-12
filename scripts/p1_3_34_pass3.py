#!/usr/bin/env python3
"""P1-3.4 pass3 — 补溯 p1_3_34_fix 漏掉的卡（正文含真实本地路径引用但被标 unknown）。

背景：p1_3_34_fix.py 的 LOCAL_RE 只匹配 readings/books/ 和 raw/ 前缀，
未匹配 /home/rayliu/... 等真实存在的本地路径 → 8 张卡被误标 unknown。
本脚本按 P1-3 规则「真实本地路径 test -f 验证」补溯。

规则：
- 只改 frontmatter 的 source 字段，不动正文与其他字段
- 候选优先级：正文明确引用的真实本地路径 / wiki 内关联卡（test -f 验证）
- 排除自引用、排除 AGENTS.md/SOUL.md 等通用文件名
- 每张处理后立即 read back 验证

用法: python3 scripts/p1_3_34_pass3.py
"""
import json, os, re

WIKI = "/home/rayliu/wiki"

# 需要补溯的卡（来自漏溯检测：unknown 且正文含可验证本地路径/关联卡）
TARGETS = {
    "discussions/C1门禁v6审计-Mimir活体测试.md": [
        "/home/rayliu/src/MimirAether/mimir-content-loop-v2.py",
    ],
    "discussions/GraphRAG7篇读后-OpenClaw使用方案.md": [
        "/home/rayliu/wiki/discussions/GraphRAG论文四方精读-7篇总收束.md",
    ],
    "discussions/GraphRAG7篇读后-四方聚焦讨论-原子化.md": [
        "/home/rayliu/wiki/discussions/GraphRAG论文四方精读-7篇总收束.md",
    ],
    "discussions/Heartbeat讨论室机制完善.md": [
        "/home/rayliu/wiki/discussions/讨论室规则.md",
    ],
    "discussions/LLM Wiki论文研讨-四方各挑一篇投票.md": [
        "/home/rayliu/wiki/concepts/harness-handbook.md",
    ],
    "discussions/Loki-Mimir-subprocess修复方案投票.md": [
        "/home/rayliu/wiki/concepts/pi-subagents-capabilities.md",
    ],
    "discussions/ML知识迁移wiki-四方讨论.md": [
        "/home/rayliu/wiki/index.md",
    ],
    "discussions/Mimir-P0执行总结.md": [
        "/home/rayliu/.mimiraether/data/trajectories/2026-08-10/b22a008295b13cb7.jsonl",
    ],
}

# 通用文件名（不作为 source）
GENERIC = {"AGENTS.md", "SOUL.md", "MEMORY.md", "SKILL.md", "README.md", "LEARNINGS.md", "CLAUDE.md", "USER.md", "index.md"}


def to_wiki_rel(p):
    """绝对路径 -> wiki 相对路径（若在 wiki 内）；否则保留绝对路径。"""
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

    # 选第一个真实存在的候选
    src = None
    for c in candidates:
        c2 = c.replace("~", "/home/rayliu")
        if os.path.exists(c2):
            base = os.path.basename(c2)
            if "/" not in c2.replace("\\", "/") and base in GENERIC:
                continue
            if c2 == path:
                continue  # 自引用
            src = to_wiki_rel(c2)
            break
    if not src:
        return {"file": rel, "action": "no-valid-candidate", "source": None}

    # 重建 frontmatter：替换/新增 source 字段（保持其他字段不变）
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

    # read back 验证
    verify = open(path, encoding="utf-8").read()
    ok = f'source: "{src}"' in verify.split("---", 2)[1] if verify.startswith("---") else False
    return {"file": rel, "action": "fixed", "source": src, "verified": ok}


def main():
    results = []
    for rel, cands in TARGETS.items():
        r = fix_one(rel, cands)
        results.append(r)
        print(f"{r['file']} | {r['action']} | {r.get('source')} | verified={r.get('verified')}")
    json.dump(results, open("/tmp/p1_3_34_pass3_results.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    from collections import Counter
    print("\n统计:", dict(Counter(r["action"] for r in results)))
    print("DONE")


if __name__ == "__main__":
    main()
