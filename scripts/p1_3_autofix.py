#!/usr/bin/env python3
"""P1-3 source 自动修复脚本（机械部分，确定性规则，不编造）。

处理对象: /home/rayliu/wiki 下 concepts/discussions/comparisons 必填类卡
规则:
  1. 复数 `sources:` 字段 -> 单数 `source:`（内联列表保持内联，合法 YAML）
  2. 缺 source 或 "待补raw" -> 从正文正则提取真实来源:
     - URL (http/https, 去重, 优先 arxiv/github)
     - 本地路径引用 (readings/... raw/...)
  3. 无任何线索 -> 保留/写入 source: "待补raw"（SCHEMA 允许占位）
  4. 只改 frontmatter 的 source/sources 行，不动正文与其他字段
  5. 修改后逐卡验证: source 字段落盘 + 本地路径 test -f 存在

用法: python3 /tmp/p1_3_autofix.py [--dry-run] [--json /tmp/p1_3_cards.json]
"""
import os, re, sys, json, glob

WIKI = "/home/rayliu/wiki"
DRY = "--dry-run" in sys.argv

URL_RE = re.compile(r"https?://[^\s\)\]\}>\"'`，。、；：|]+")
ARXIV_RE = re.compile(r"https?://(?:www\.)?arxiv\.org/(?:abs|pdf)/[\d.]+")
GH_RE = re.compile(r"https?://github\.com/[A-Za-z0-9_.\-/]+")
LOCAL_RE = re.compile(r"(?:readings/books/[^\s\)\]\}>\"'`，。、；：|]+\.md|raw/[^\s\)\]\}>\"'`，。、；：|]+\.(?:md|pdf|txt|json))")

BAD_URL_HINTS = ("127.0.0.1", "localhost", "rsproxy", "example.com")


def path_exists(p):
    """路径存在性: 支持 ~ 展开 + wiki 相对路径。"""
    if not p:
        return False
    p2 = os.path.expanduser(p)
    if p2.startswith("/"):
        return os.path.exists(p2)
    return os.path.exists(os.path.join(WIKI, p2))


def clean_url(u):
    """清理 URL: 去尾部标点/反引号, 过滤明显非来源。"""
    u = u.rstrip(".,;:)]}>`")
    if any(h in u for h in BAD_URL_HINTS):
        return None
    if re.search(r"[\u4e00-\u9fff]", u):
        return None
    if "`" in u or " " in u:
        return None
    return u


def pick_sources(body):
    """从正文提取真实来源: URL 优先 arxiv/github, 然后本地路径引用。"""
    arxiv = ARXIV_RE.findall(body)
    gh = GH_RE.findall(body)
    urls = URL_RE.findall(body)
    cands = []
    for u in arxiv + gh + urls:
        u = clean_url(u)
        if u and u not in cands:
            cands.append(u)
    locals_ = []
    for p in LOCAL_RE.findall(body):
        p = p.rstrip(".,;:])}`") or p
        if p not in locals_ and path_exists(p):
            locals_.append(p)
    return cands[:3], locals_[:2]


def find_fm_region(text):
    """返回 (frontmatter行list, 结束行号) 或 None。"""
    if not text.startswith("---"):
        return None
    lines = text.splitlines()
    end = None
    for i in range(1, min(len(lines), 60)):
        if lines[i].strip() == "---":
            end = i
            break
    if end is None:
        return None
    return lines[1:end], end


def fix_file(rel):
    path = os.path.join(WIKI, rel)
    text = open(path, encoding="utf-8").read()
    region = find_fm_region(text)
    if region is None:
        return {"file": rel, "action": "skip-no-frontmatter", "source": None}
    fm_lines, end = region
    lines = fm_lines[:]
    action = None
    new_source = None
    bad_value = None
    src_idx = None

    # 1) 复数 -> 单数
    pl_idx = [i for i, l in enumerate(lines) if re.match(r"^sources\s*:", l)]
    s_idx = [i for i, l in enumerate(lines) if re.match(r"^source\s*:", l)]

    if pl_idx:
        i = pl_idx[0]
        val = lines[i].split(":", 1)[1].strip()
        if not val:
            action = "empty"
        else:
            items = []
            if val.startswith("["):
                inner = val.strip()[1:-1]
                items = [x.strip().strip('"').strip("'") for x in inner.split(",")] if inner.strip() else []
            else:
                items = [val.strip().strip('"').strip("'")]
            bad = [v for v in items if v and not v.startswith("http") and not path_exists(v) and v != "待补raw"]
            if bad:
                action = "plural-bad"
                bad_value = bad
            else:
                action = "renamed"
                new_source = items
                src_idx = i
    elif s_idx:
        i = s_idx[0]
        val = lines[i].split(":", 1)[1].strip()
        if not val or val in ('""', "''"):
            action = "empty"
        elif val.strip('"').strip("'") == "待补raw":
            urls, locals_ = pick_sources(text)
            if urls or locals_:
                action = "replaced-placeholder"
                new_source = (urls + locals_)[:3]
            else:
                action = "placeholder-kept"
                new_source = ["待补raw"]
        else:
            vals = [val.strip('"').strip("'")]
            bad = [v for v in vals if v and not v.startswith("http") and not path_exists(v)]
            if bad:
                action = "fake"
                bad_value = bad
            else:
                return {"file": rel, "action": "ok", "source": None}
    else:
        urls, locals_ = pick_sources(text)
        if urls or locals_:
            action = "added"
            new_source = (urls + locals_)[:3]
        else:
            action = "placeholder"
            new_source = ["待补raw"]

    if action in ("plural-bad", "fake", "empty"):
        return {"file": rel, "action": action, "source": None, "bad": bad_value}

    # 构造新 frontmatter
    if src_idx is not None:  # renamed: 仅替换行首字段名
        lines[src_idx] = "source:" + lines[src_idx].split(":", 1)[1].rstrip("\n")
    else:
        insert_at = None
        for i, l in enumerate(lines):
            if re.match(r"^tags\s*:", l):
                insert_at = i + 1
                break
        if insert_at is None:
            insert_at = len(lines)
        if len(new_source) == 1:
            line = 'source: "' + new_source[0] + '"'
        else:
            line = "source:\n" + "\n".join('  - "' + s + '"' for s in new_source)
        lines.insert(insert_at, line)

    new_fm = "\n".join(lines)
    new_text = "---\n" + new_fm + "\n---\n" + "\n".join(text.splitlines()[end + 1:])

    if not DRY:
        open(path, "w", encoding="utf-8").write(new_text)
        # 验证
        verify = open(path, encoding="utf-8").read()
        if re.search(r"^source\s*:", verify, re.M) is None:
            return {"file": rel, "action": "VERIFY-FAIL", "source": new_source}
        for s in new_source:
            if not s.startswith("http") and s != "待补raw" and not path_exists(s):
                return {"file": rel, "action": "VERIFY-FAIL", "source": new_source}
    return {"file": rel, "action": action, "source": new_source}


def main():
    cards = json.load(open("/tmp/p1_3_cards.json", encoding="utf-8"))
    # 只处理必填类（concepts/discussions/comparisons）
    targets = [c for c in cards if c["file"].split("/")[0] in ("concepts", "discussions", "comparisons")]
    results = []
    for c in targets:
        r = fix_file(c["file"])
        results.append(r)

    from collections import Counter
    counter = Counter(r["action"] for r in results)
    print("DRY-RUN" if DRY else "EXECUTED")
    print("动作分布:", dict(counter))
    for r in results:
        if r["action"] in ("renamed", "added", "replaced-placeholder", "placeholder", "placeholder-kept"):
            print(f"  {r['action']:20s} {r['file']} -> {r['source']}")
        elif r["action"] in ("plural-bad", "fake", "empty"):
            print(f"  {r['action']:20s} {r['file']} !! 需LLM: {r.get('bad')}")
    json.dump(results, open("/tmp/p1_3_autofix_results.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    main()
