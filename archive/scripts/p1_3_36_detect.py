#!/usr/bin/env python3
"""A7/P1-3.6 pass3 检测 — 对全部当前占位卡（discussions + entities）扫描正文候选
（真实本地路径 / wiki 关联卡 / markdown 链接 / 外部 URL），test -f/-d 验证，
输出每卡线索判定，供补溯人工确认。"""
import os, re, sys, datetime

WIKI = os.environ.get("MIMIR_WIKI_ROOT", os.path.expanduser("~/wiki"))
DIRS = ["discussions", "entities"]

# 与 p1_3_36_scan.py 相同的排除清单
EXCLUDE = {
    "discussions/2026-08-12-Hermes派发-P1-3.5.md",
    "discussions/2026-08-12-Hermes派发-P1-3.4.md",
    "discussions/2026-08-12-Hermes派发-P1-3.6.md",
    "discussions/2026-08-12-Mimir-P1-3.4-@hermes信号.md",
    "discussions/2026-08-12-Mimir-P1-3.3-@hermes信号.md",
    "discussions/2026-08-12-Mimir-P1-3.2-@hermes信号.md",
    "discussions/2026-08-12-Mimir-P1-3-source补齐-@hermes信号.md",
    "discussions/P1-2-source统一报告-@hermes信号卡.md",
    "discussions/2026-08-12-Mimir-P1-2-source统一-@hermes信号.md",
    "discussions/Mimir-P1-3-source补齐报告.md",
    "discussions/Mimir-P1-3-source补源报告.md",
    "discussions/todo与遗留问题四方讨论.md",
    "discussions/RAW统一方案四方讨论.md",
    "discussions/Mimir容量与行为改革四方讨论.md",
    "discussions/2026-08-12-Mimir-P1-3.5-@hermes信号.md",
    "discussions/2026-08-12-Mimir-A1压缩启用-@hermes信号.md",
    "discussions/2026-08-12-Mimir-A3-max_turns分档-@hermes信号.md",
    "discussions/2026-08-12-Mimir-A4-规则架构审计-@hermes信号.md",
    "discussions/2026-08-12-Hermes巡游-A4执行中-todo运行时修复未生效.md",
    "discussions/2026-08-12-Mimir-修todo工具接线bug-@hermes信号.md",
}

LOCAL_PATH_RE = re.compile(
    r"(?:/home/rayliu|~)/[^\s\)\]\}>\"'`，。、；：|]+"
    r"|\.mimiraether/[^\s\)\]\}>\"'`，。、；：|]+"
    r"|src/MimirAether/[^\s\)\]\}>\"'`，。、；：|]+"
    r"|wiki/(?:concepts|discussions|entities|raw|readings)/[^\s\)\]\}>\"'`，。、；：|]+\.md"
)
WIKILINK_RE = re.compile(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]")
MDLINK_RE = re.compile(r"\[[^\]]+\]\(([^)#]+?)(?:\.md)?\)")
URL_RE = re.compile(r"https?://[^\s\)\]\}>\"'`，。、；：|]+")
GENERIC = {"AGENTS.md", "SOUL.md", "MEMORY.md", "SKILL.md", "README.md", "LEARNINGS.md", "CLAUDE.md", "USER.md", "index.md"}

PLACEHOLDER_RE = re.compile(r"待补raw|unknown（待溯源）|unknown\(待溯源\)|待溯源|占位|TBD|待补")


def extract_source(text):
    if not text.startswith("---"):
        return None, True
    lines = text.splitlines()
    end = None
    for i in range(1, min(len(lines), 60)):
        if lines[i].strip() == "---":
            end = i
            break
    if end is None:
        return None, True
    fm_lines = lines[1:end]
    vals = []
    in_src = False
    for l in fm_lines:
        if re.match(r"^sources?\s*:", l):
            in_src = True
            rest = l.split(":", 1)[1].strip()
            if rest:
                vals.append(rest)
            continue
        if in_src:
            if re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*\s*:", l):
                in_src = False
            elif l.strip().startswith("-"):
                vals.append(l.strip()[1:].strip())
            else:
                if l.strip():
                    vals.append(l.strip())
    if not vals:
        return None, True
    joined = " ".join(vals)
    return joined, bool(PLACEHOLDER_RE.search(joined))


def find_candidates(rel, text):
    """返回 verified=True 的候选列表（路径/链接真实存在）。"""
    lines = text.splitlines()
    end = None
    for i in range(1, min(len(lines), 60)):
        if lines[i].strip() == "---":
            end = i
            break
    body = "\n".join(lines[end + 1:]) if end else text

    cands = []  # (kind, target, exists)
    seen = set()

    for m in LOCAL_PATH_RE.finditer(body):
        p = m.group(0).rstrip(".,;:])}`\"")
        key = ("path", p)
        if key in seen:
            continue
        seen.add(key)
        c2 = p.replace("~", "/home/rayliu")
        exists = os.path.exists(c2)
        # 排除泛化文件名（无目录限定）
        if exists and os.path.basename(c2) in GENERIC and "/" not in c2.replace("\\", "/"):
            exists = False
        cands.append(("path", p, exists))

    for m in WIKILINK_RE.finditer(text):
        tgt = m.group(1).strip().replace("\\", "/")
        base = rel.split("/")[-1].replace(".md", "")
        if tgt.replace(".md", "") == base:
            continue
        key = ("wikilink", tgt)
        if key in seen:
            continue
        seen.add(key)
        # 解析: wiki 相对路径或绝对
        t2 = tgt.replace("~", "/home/rayliu")
        if t2.startswith("/"):
            exists = os.path.exists(t2)
        else:
            exists = os.path.exists(os.path.join(WIKI, t2)) or os.path.exists(
                os.path.join(WIKI, t2 + ".md"))
        cands.append(("wikilink", tgt, exists))

    for m in MDLINK_RE.finditer(body):
        tgt = m.group(1).strip()
        if tgt.startswith("http") or tgt.startswith("#"):
            continue
        key = ("mdlink", tgt)
        if key in seen:
            continue
        seen.add(key)
        t2 = tgt.replace("~", "/home/rayliu")
        if t2.startswith("/"):
            exists = os.path.exists(t2)
        else:
            exists = os.path.exists(os.path.join(WIKI, t2)) or os.path.exists(
                os.path.join(WIKI, t2 + ".md"))
        cands.append(("mdlink", tgt, exists))

    for m in URL_RE.finditer(body):
        u = m.group(0).rstrip(".,;:])}`\"")
        key = ("url", u)
        if key in seen:
            continue
        seen.add(key)
        cands.append(("url", u, True))  # URL 视为候选（需 web 验证）

    return cands


def main():
    placeholders = []
    for d in DIRS:
        full = os.path.join(WIKI, d)
        if not os.path.isdir(full):
            continue
        for fn in sorted(os.listdir(full)):
            if not fn.endswith(".md"):
                continue
            rel = f"{d}/{fn}"
            if rel in EXCLUDE:
                continue
            text = open(os.path.join(full, fn), encoding="utf-8").read()
            src, ph = extract_source(text)
            if ph:
                placeholders.append((rel, text))

    print(f"占位卡总数: {len(placeholders)}\n")
    for rel, text in sorted(placeholders):
        cands = find_candidates(rel, text)
        verified = [c for c in cands if c[2]]
        unverified = [c for c in cands if not c[2]]
        mt = datetime.datetime.fromtimestamp(os.path.getmtime(os.path.join(WIKI, rel))).strftime("%m-%d %H:%M")
        flag = "🔴有线索" if verified else "⚪无线索"
        print(f"{flag} [{mt}] {rel}")
        for kind, t, ex in verified[:6]:
            print(f"    ✅ {kind}: {t[:120]}")
        if unverified and not verified:
            for kind, t, ex in unverified[:3]:
                print(f"    ❌ {kind}: {t[:120]}")


if __name__ == "__main__":
    main()
