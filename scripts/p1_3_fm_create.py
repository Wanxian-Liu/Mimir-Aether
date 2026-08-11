#!/usr/bin/env python3
"""P1-3 为无 frontmatter 卡创建合法 frontmatter（title/created/updated/type/tags/source）。

规则:
  - title: 首个 # 标题（去 #，去 markdown 强调）
  - created/updated: 正文日期线索（2026-xx-xx）优先，否则 git 首次提交日期，否则今天
  - type: concepts -> concept / discussions -> discussion
  - tags: 默认 [report] 或按类型
  - source: 正文候选（find_candidates 逻辑）或 "待补raw"
  - 只插 frontmatter，正文不动
"""
import os, re, subprocess, json

WIKI = "/home/rayliu/wiki"

URL_RE = re.compile(r"https?://[^\s\)\]\}>\"'`，。、；：|]+")
ARXIV_RE = re.compile(r"arXiv\s*:\s*([\d.]+)", re.I)
DATE_RE = re.compile(r"(20\d{2})[-/年](\d{1,2})[-/月](\d{1,2})")
LINK_RE = re.compile(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]")
BAD_URL_HINTS = ("127.0.0.1", "localhost", "rsproxy", "example.com")


def path_exists(p):
    p2 = os.path.expanduser(p)
    if p2.startswith("/"):
        return os.path.exists(p2)
    return os.path.exists(os.path.join(WIKI, p2))


def clean_url(u):
    u = u.rstrip(".,;:)]}>`*，。、；：）】」』") or u
    u = re.sub(r"[）→」】].*$", "", u)
    if any(h in u for h in BAD_URL_HINTS):
        return None
    if re.search(r"[\u4e00-\u9fff]", u):
        return None
    if "`" in u or " " in u:
        return None
    return u


def git_first_date(rel):
    try:
        out = subprocess.run(
            ["git", "log", "--diff-filter=A", "--format=%ad", "--date=short", "--", rel],
            capture_output=True, text=True, cwd=WIKI, timeout=10,
        ).stdout.strip().splitlines()
        return out[0] if out else None
    except Exception:
        return None


def find_source(text):
    cands = []
    for m in ARXIV_RE.finditer(text):
        c = f"https://arxiv.org/abs/{m.group(1)}"
        if c not in cands:
            cands.append(c)
    for u in URL_RE.findall(text):
        c = clean_url(u)
        if c and c not in cands:
            cands.append(c)
    for m in LINK_RE.finditer(text):
        tgt = m.group(1).strip()
        for prefix in ("discussions/", "concepts/", "entities/", "comparisons/"):
            cand = prefix + tgt
            if not cand.endswith(".md"):
                cand += ".md"
            if cand not in cands and path_exists(cand):
                cands.append(cand)
    return cands[:3]


def extract_date(text):
    m = DATE_RE.search(text)
    if m:
        return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    return None


def main():
    targets = [
        # entities no-frontmatter
        "entities/Agency-Agent角色索引.md",
        "entities/Mimir行为观察日志.md",
        "entities/Pi-Agent-agent-core-module.md",
        "entities/Pi-Agent-ai-module.md",
        "entities/Pi-Agent-coding-agent-module.md",
        "entities/Pi-Agent-tui-module.md",
        "entities/Pi-Agent.md",
        "entities/WV索引.md",
        "entities/index.md",
        # concepts no-frontmatter（已处理，保留幂等）
        "concepts/Mimir-P1-1-source规范报告.md",
        "concepts/Mimir-P1-2-source统一报告.md",
        "concepts/Mimir-delegate-bug修复报告.md",
        "concepts/Mimir-双写修复报告.md",
        "concepts/四方完成信号机制.md",
        "discussions/18bug第二轮-Buzz四方讨论记录.md",
        "discussions/2026-08-12-Mimir-P1-2-source统一-@hermes信号.md",
        "discussions/GraphRAG论文四方精读讨论.md",
        "discussions/Mimir-MEMORY方案.md",
        "discussions/Mimir身份文件优化方案.md",
        "discussions/OpenClaw备份83GB自查-安全审计.md",
        "discussions/OpenClaw真心话-当AI懂得问.md",
        "discussions/dispatcher-trigger-playbook.md",
        "discussions/freeze-log.md",
        "discussions/on-demand-heartbeat-protocol.md",
        "discussions/可视化工作台-Harness执行计划.md",
        "discussions/当AI懂得问-mimir.md",
        "discussions/技能迭代批次-执行记录.md",
        "discussions/讨论室自身Bug审计-四方集体找茬.md",
        "discussions/读书体系迁移审计-四方会议.md",
    ]
    today = "2026-08-12"
    for rel in targets:
        path = os.path.join(WIKI, rel)
        text = open(path, encoding="utf-8").read()
        if text.startswith("---"):
            print(f"  skip(已有fm) {rel}")
            continue
        # title
        m = re.search(r"^#\s+(.+)$", text, re.M)
        title = m.group(1).strip().strip("`").strip("*") if m else os.path.basename(rel).replace(".md", "")
        # date
        d = extract_date(text) or git_first_date(rel) or today
        # type
        kind = "concept" if rel.startswith("concepts/") else "discussion"
        # source
        srcs = find_source(text)
        fm_lines = ["---", f'title: "{title}"', f"created: {d}", f"updated: {d}", f"type: {kind}", "tags: [report]"]
        if srcs:
            if len(srcs) == 1:
                fm_lines.append(f'source: "{srcs[0]}"')
            else:
                fm_lines.append("source:")
                fm_lines += [f'  - "{s}"' for s in srcs]
        else:
            fm_lines.append('source: "待补raw"')
        fm_lines.append("---")
        new_text = "\n".join(fm_lines) + "\n" + text
        open(path, "w", encoding="utf-8").write(new_text)
        print(f"  ✅ {rel} | title={title[:30]} | source={srcs or ['待补raw']}")

    # 验证
    print("\n=== 验证 ===")
    for rel in targets:
        text = open(os.path.join(WIKI, rel), encoding="utf-8").read()
        ok = text.startswith("---") and re.search(r"^source\s*:", text, re.M)
        print(f"  {'✅' if ok else '❌'} {rel}")


if __name__ == "__main__":
    main()
