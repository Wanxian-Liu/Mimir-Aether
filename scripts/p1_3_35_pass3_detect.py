#!/usr/bin/env python3
"""P1-3.5 pass3 检测 — 对 15 张被标 unknown 的卡扫描正文候选（真实本地路径 / wiki 关联卡），
输出 test -f 验证结果，供 pass3 补溯人工确认。"""
import os, re, json

WIKI = "/home/rayliu/wiki"

CARDS = [
    "discussions/Mimir-P0执行报告-自我审计.md",
    "discussions/MimirGateway身份矛盾调查.md",
    "discussions/Mimir不落盘-架构根因深挖.md",
    "discussions/Mimir体检-C1效果验证.md",
    "discussions/Mimir原子整改清单-四方逐项投票.md",
    "discussions/Mimir双循环架构-根因与修复.md",
    "discussions/Mimir可靠性专项-四方会诊.md",
    "discussions/Mimir向Hermes学习-实验讨论.md",
    "discussions/Mimir学Hermes-第一学习点选定.md",
    "discussions/Mimir学习成果审视-四方会议.md",
    "discussions/Mimir整改B组-四方讨论.md",
    "discussions/Mimir整改C组-机制修复四方讨论.md",
    "discussions/Mimir整改二次讨论-执行前验证.md",
    "discussions/Mimir整改执行记录.md",
    "discussions/Mimir核心体检-1循环执行.md",
]

# 本地路径模式：/home/rayliu/...、~/...、wiki 相对路径、src 路径、.mimiraether 路径
LOCAL_PATH_RE = re.compile(
    r"(?:/home/rayliu|~)/[^\s\)\]\}>\"'`，。、；：|]+"
    r"|\.mimiraether/[^\s\)\]\}>\"'`，。、；：|]+"
    r"|src/MimirAether/[^\s\)\]\}>\"'`，。、；：|]+"
    r"|wiki/(?:concepts|discussions|entities|raw|readings)/[^\s\)\]\}>\"'`，。、；：|]+\.md"
)
WIKILINK_RE = re.compile(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]")
MDLINK_RE = re.compile(r"\[[^\]]+\]\(([^)#]+?)(?:\.md)?\)")
GENERIC = {"AGENTS.md", "SOUL.md", "MEMORY.md", "SKILL.md", "README.md", "LEARNINGS.md", "CLAUDE.md", "USER.md", "index.md"}


def main():
    for rel in CARDS:
        path = os.path.join(WIKI, rel)
        text = open(path, encoding="utf-8").read()
        lines = text.splitlines()
        end = None
        for i in range(1, min(len(lines), 60)):
            if lines[i].strip() == "---":
                end = i
                break
        body = "\n".join(lines[end + 1:]) if end else text

        cands = set()
        # 本地路径
        for m in LOCAL_PATH_RE.finditer(body):
            p = m.group(0).rstrip(".,;:])}`")
            cands.add(("path", p))
        # wikilink
        for m in WIKILINK_RE.finditer(text):
            tgt = m.group(1).strip().replace("\\", "/")
            base = rel.split("/")[-1].replace(".md", "")
            if tgt.replace(".md", "") == base:
                continue
            cands.add(("wikilink", tgt))
        # markdown 链接
        for m in MDLINK_RE.finditer(body):
            tgt = m.group(1).strip()
            if tgt.startswith("http") or tgt.startswith("#"):
                continue
            cands.add(("mdlink", tgt))

        print(f"\n===== {rel} =====")
        found_any = False
        for kind, c in sorted(cands):
            # 解析为绝对路径测试
            c2 = c.replace("~", "/home/rayliu")
            if c2.startswith("/"):
                exists = os.path.exists(c2)
                if exists and os.path.basename(c2) in GENERIC and "/" not in c2.replace("\\", "/"):
                    continue
            else:
                # wiki 相对
                exists = os.path.exists(os.path.join(WIKI, c2))
                if not exists:
                    for prefix in ("concepts/", "discussions/", "entities/", "comparisons/"):
                        cc = prefix + c2
                        if not cc.endswith(".md"):
                            cc += ".md"
                        if os.path.exists(os.path.join(WIKI, cc)):
                            c2 = cc
                            exists = True
                            break
            if exists:
                found_any = True
                print(f"  [{kind}] EXISTS: {c}  ->  {c2}")
            else:
                print(f"  [{kind}] missing: {c}")
        if not found_any:
            print("  (无任何存在的候选)")


if __name__ == "__main__":
    main()
