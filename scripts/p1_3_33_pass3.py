#!/usr/bin/env python3
"""P1-3.3 pass3 — 补溯 p1_3_33_fix 漏掉的卡（正文含真实本地路径引用但被标 unknown）。

背景：p1_3_33_fix.py 的 LOCAL_RE 只匹配 readings/books/ 和 raw/ 前缀，
未匹配 /.openclaw/projects/... 等真实存在的本地路径 → 14 张卡被误标 unknown。
本脚本按 P1-3 规则「真实本地路径 test -f 验证」补溯。

规则：
- 只改 frontmatter 的 source 字段，不动正文与其他字段
- 候选优先级：wiki 内关联卡 > 真实本地路径（test -f 验证）
- 排除自引用、排除 AGENTS.md/SOUL.md 等通用文件名
- 每张处理后立即 read back 验证

用法: python3 scripts/p1_3_33_pass3.py
"""
import json, os, re

WIKI = "/home/rayliu/wiki"

# 需要补溯的卡（来自漏溯检测：unknown 且正文含可验证本地路径）
TARGETS = {
    "concepts/hermes-moa-memory-lsp-learning.md": ["/home/rayliu/.hermes/SOUL.md"],
    "discussions/12项诊断-#5-#10-OpenClaw妹-执行报告-2026-07-27.md": [
        "/home/rayliu/wiki/discussions/讨论室规则.md",
        "/home/rayliu/.openclaw/workspace/memory/2026-07-27.md",
    ],
    "discussions/18bug修复执行-四方会诊.md": [
        "/home/rayliu/.openclaw/projects/agency-agents/testing/testing-reality-checker.md",
    ],
    "discussions/18bug第二轮-Buzz四方讨论记录.md": [
        "/home/rayliu/wiki/discussions/世界模型审计-18bug集体修复.md",
    ],
    "discussions/2026-07-31-Loki根因调查-体检报告.md": [
        "/home/rayliu/wiki/discussions/Mimir写后未落地-根因分析.md",
        "/home/rayliu/wiki/discussions/找回健康的Mimir.md",
        "/home/rayliu/.openclaw/workspace-loki/MEMORY.md",
    ],
    "discussions/2026-08-12-Mimir-P1-2-source统一-@hermes信号.md": [
        "/home/rayliu/wiki/concepts/Mimir-P1-2-source统一报告.md",
    ],
    "discussions/2026-08-12-Mimir-P1-3-source补齐-@hermes信号.md": [
        "/home/rayliu/wiki/concepts/Mimir-P1-3-source补齐报告.md",
    ],
    "discussions/300088四方角色研究-第一次实战.md": [
        "/home/rayliu/.openclaw/projects/agency-agents/testing/testing-evidence-collector.md",
        "/home/rayliu/.openclaw/projects/agency-agents/testing/testing-reality-checker.md",
    ],
    "discussions/300088实战复盘-四方反思.md": [
        "/home/rayliu/wiki/discussions/300088四方角色研究-第一次实战.md",
        "/home/rayliu/.openclaw/projects/agency-agents/testing/testing-reality-checker.md",
    ],
    "discussions/316角色分配模式-四方讨论.md": [
        "/home/rayliu/.openclaw/projects/agency-agents/specialized/automation-governance-architect.md",
        "/home/rayliu/.openclaw/projects/agency-agents/specialized/change-management-consultant.md",
    ],
    "discussions/Agency Agent体系-待办2下沉角色.md": [
        "/home/rayliu/.openclaw/projects/agency-agents/specialized/automation-governance-architect.md",
        "/home/rayliu/.openclaw/projects/agency-agents/testing/testing-reality-checker.md",
    ],
    "discussions/Agency Agent体系落地-四方讨论总卡.md": [
        "/home/rayliu/.openclaw/projects/agency-agents/specialized/automation-governance-architect.md",
    ],
    "discussions/Agency Agent角色分配-四方认领.md": [
        "/home/rayliu/wiki/discussions/Mimir不落盘-架构根因深挖.md",
        "/home/rayliu/.openclaw/projects/agency-agents/testing/testing-reality-checker.md",
    ],
    "discussions/B组复盘-删改审慎-四方再讨论.md": [
        "/home/rayliu/.openclaw/projects/agency-agents/testing/testing-reality-checker.md",
        "/home/rayliu/.openclaw/projects/agency-agents/engineering/engineering-software-architect.md",
    ],
}

# 通用文件名（不作为 source）
GENERIC = {"AGENTS.md", "SOUL.md", "MEMORY.md", "SKILL.md", "README.md", "LEARNINGS.md", "CLAUDE.md", "USER.md"}


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
            # 只有裸文件名（无目录）才可能是通用文件误引用；带目录的绝对路径可信
            if "/" not in c2.replace("\\", "/") and base in GENERIC:
                continue
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
    json.dump(results, open("/tmp/p1_3_33_pass3_results.json", "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    from collections import Counter
    print("\n统计:", dict(Counter(r["action"] for r in results)))
    print("DONE")


if __name__ == "__main__":
    main()
