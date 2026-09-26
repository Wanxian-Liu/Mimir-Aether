#!/usr/bin/env python3
"""Wiki 质量门禁 —— 报告层（零 LLM · B2 script 形态 · 2026-09-26）。

为什么有这一层（根因，不是洁癖）：
    本 job 原为 **agent 形态**（`script: None` + 563 字符 prompt）。2026-09-22 20:00 起
    上游 402 使 agent run 只返回 49 字节兜底文本，台账仍记 `last_status=ok`
    / `last_delivery_ok=true` —— 「调度在跑、投递在跑、检查没跑」。改成 script 形态
    后：**零 LLM**（402 暴露面归零、省 2 次 run/日）、**判据可复算**、**失败真改退出码**。

    判定逻辑写在这里而不是 home 的 `~/.mimiraether/scripts/*`（那层不进版本控制），
    避免重演「在跑版 != 版本控制版」（audit_send_paths.py 前例）。

作用域纪律（本次修的主体）：
    旧门禁（home 侧 wiki-quality-gate.sh）的注释与实际不符，产生三类稳定假阳性：
      1. 用 grep -roP 扫**所有文件**（不限 .md）
         => 非 md 文件里的 bash [[ ... ]] 被判成 wikilink；
      2. **不跳过代码块/行内代码** => 文档里「举例说明」的链接被判成死链
         （与 check_dead_refs.py 注释扫全文同型；那一类刚从 FAIL 修成 PASS）；
      3. 重复页检测用 glob -name "*-*.md" => 只看得见含连字符的名字，
         漏报「无连字符重名」与「空格 vs 连字符」同页变体。
    本文件把这三条按**声明的作用域**收回：只扫 .md、跳过代码、按归一化名判重/判存在。

范围（显式声明，避免「零问题」被外推）：
    默认只扫**策展层** concepts/ entities/ comparisons/ queries/ llmvt/ readings/。
    不含 raw/（第三方导入内容，链接相对其自身体系）、discussions/（历史留痕、
    含大量举例链接）、archive/、drafts/、_attachments/、data/。
    可用 --paths 覆盖；报告首行打印实际扫描面与文件数。

退出码：
    0 = 门禁跑完（无论有无 issue —— issue 是本层正常产出，不是门禁故障）
    2 = **门禁自己没跑成**（wiki 目录缺失 / 扫到 0 个页面 / 不可读）
        => 刻意让「仪表死掉」进 cron 台账 error，而不是记 ok。这正是假绿族的修法。
    --strict 可让「有 issue」也返回 1（留给以后改判，不必重构）。
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import os
import re
import sys
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Set, Tuple


def _os_home() -> Path:
    """操作系统层家目录。

    本机 HOME 语义是双的（agent 沙箱里 HOME 就是 mimir home，实测），
    home 名恰为 .mimiraether 时上溯一层 —— 与 RS19 那族修复同一纪律。
    """
    home = Path.home()
    return home.parent if home.name == ".mimiraether" else home


def default_wiki() -> Path:
    """默认 wiki 根：env WIKI_DIR > <os home>/wiki。

    为什么不写成常量字面量：把真实用户名/家目录写进**公开仓**会被 pre-push 路径闸
    拦下（那道闸是对的）。生产路径由 home 壳显式 --wiki 传入，公开仓只留可推导形式。
    """
    env = os.environ.get("WIKI_DIR")
    if env:
        return Path(env)
    return _os_home() / "wiki"

DEFAULT_LAYERS: Tuple[str, ...] = ("concepts", "entities", "comparisons", "queries", "llmvt", "readings")
EXCLUDED_DIRS = ("raw", "discussions", "archive", "drafts", "_attachments", "data", ".git", "state-snapshots")

# 语法占位符：文档里「举例说明链接形态」用的词，不是真实页面名。
# 为什么要显式列出：把「过滤掉什么」写进判据真源并计数，而不是靠肉眼无视告警
#   （与 check_dead_refs.py 的散文假阳性同族）。
PLACEHOLDER_TARGETS = frozenset({"x", "file", "page", "target", "link", "wikilink", "path", "url"})
# 每个目录下的约定名，不是「同页重复」；旧 glob 判重把 README 判成 8 组重复。
CONVENTIONAL_STEMS = frozenset({"readme", "index", "log", "schema", "agents", "todo", "inbox"})

LINK_RE = re.compile(r"\[\[([^\[\]]+)\]\]")
FENCE_RE = re.compile(r"^\s*(```|~~~)")
INLINE_CODE_RE = re.compile(r"`[^`\n]*`")


def normalize(name: str) -> str:
    """归一化页面名：小写、空格/下划线 -> 连字符、折叠多个连字符。

    这是「空格 vs 连字符」同页变体与大小写变体的判据真源。
    """
    s = name.strip().lower()
    s = s.replace("_", "-").replace(" ", "-")
    s = re.sub(r"-{2,}", "-", s)
    return s.strip("-")


def strip_code(text: str) -> str:
    """移除围栏代码块与行内代码，**保持行号不变**（换行保留）。

    为什么要保持行结构：死链报告要给出源文件行号，行号错位会让溯源失效。
    """
    out: List[str] = []
    in_fence = False
    for line in text.split("\n"):
        if FENCE_RE.match(line):
            in_fence = not in_fence
            out.append("")
            continue
        if in_fence:
            out.append("")
            continue
        out.append(INLINE_CODE_RE.sub(" ", line))
    return "\n".join(out)


def _iter_md(wiki: Path, layers: Sequence[str]) -> List[Path]:
    """按层收集 .md；层不存在则跳过（并计入缺失层，供报告披露）。"""
    files: List[Path] = []
    for layer in layers:
        root = wiki / layer
        if not root.is_dir():
            continue
        for p in root.rglob("*.md"):
            if any(part in EXCLUDED_DIRS for part in p.parts):
                continue
            if p.is_file():
                files.append(p)
    return sorted(files)


def _layer_summary(wiki: Path, layers: Sequence[str]) -> Tuple[List[str], List[str]]:
    present = [l for l in layers if (wiki / l).is_dir()]
    missing = [l for l in layers if not (wiki / l).is_dir()]
    return present, missing


def _iter_all_md(wiki: Path) -> List[Path]:
    """解析面：整个 wiki 的 .md（排除 raw/discussions/archive 等）。

    为什么解析面 != 扫描面：链到 `SCHEMA.md`（wiki 根）或 `learning/spec.md`
    （非策展层）都是**合法链接**。若只按扫描面建索引，会稳定误报成死链
    —— 实测该口径差异一项就占旧报告 16/20 条。
    """
    files: List[Path] = []
    for p in wiki.rglob("*.md"):
        if any(part in EXCLUDED_DIRS for part in p.parts):
            continue
        if p.is_file():
            files.append(p)
    return sorted(files)


def build_index(files: Iterable[Path]) -> Dict[str, List[str]]:
    """归一化名 -> 文件路径集合。同时收录「带父目录」的相对键（[[entities/x]]）。"""
    index: Dict[str, List[str]] = {}
    for f in files:
        for key in (normalize(f.stem), normalize(f.parent.name + "/" + f.stem)):
            index.setdefault(key, []).append(str(f))
    return index


def find_duplicates(scan_files: Sequence[Path], wiki: Path) -> Tuple[List[Tuple[str, List[str]]], List[Tuple[str, List[str]]]]:
    """返回 (同目录同页重复, 同名跨目录)。

    判据收紧（旧版是稳定假阳性）：
      * 旧法按「去目录后同名」判 => README/index 这类每目录约定名被报成重复
        （实测 8 + 2 组假阳性），跨层同名（concepts/X 与 entities/X）也被报出。
      * 本判据只把**同一目录下、归一化后同名**视为真重复（这就是「空格 vs 连字符」
        同页变体那一类）；跨目录同名只作**信息级**计数，不计入问题。
    """
    by_dir: Dict[Tuple[str, str], List[str]] = {}
    by_scope: Dict[Tuple[str, str], List[str]] = {}
    for f in scan_files:
        stem = normalize(f.stem)
        if stem in CONVENTIONAL_STEMS:
            continue
        by_dir.setdefault((str(f.parent), stem), []).append(str(f))
        try:
            scope = f.relative_to(wiki).parts[0]     # 层 = wiki 下第一段
        except ValueError:
            scope = f.parent.name
        by_scope.setdefault((scope, stem), []).append(str(f))

    real = [(k[1], sorted(set(v))) for k, v in sorted(by_dir.items()) if len(set(v)) >= 2]
    cross = [(k[1], sorted(set(v))) for k, v in sorted(by_scope.items()) if len(set(v)) >= 2]
    cross_keys = {k for k, _ in real}
    cross = [(k, v) for k, v in cross if k not in cross_keys]
    return real, cross


def find_broken_links(files: Sequence[Path], index: Dict[str, List[str]]) -> Tuple[List[Dict[str, object]], int]:
    """死链 = [[target]] 的归一化名不在索引里。

    返回 (死链列表, 被占位符过滤器跳过的条数)。
    跳过：空目标、纯锚点 [[#x]]、带协议的外链、行内代码/围栏代码块内的内容、
          **语法占位符**（PLACEHOLDER_TARGETS，如 [[file#x]] 这种举例形态）。
    别名形式 [[page|显示名]] 取 page；带锚点 [[page#x]] 取 page。
    """
    broken: List[Dict[str, object]] = []
    skipped = 0
    for f in files:
        try:
            raw = f.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        text = strip_code(raw)
        for lineno, line in enumerate(text.split("\n"), start=1):
            for m in LINK_RE.finditer(line):
                inner = m.group(1)
                target = inner.split("|")[0].strip()
                if not target or target.startswith("#"):
                    continue
                if "://" in target or target.startswith("mailto:"):
                    continue
                target = target.split("#")[0].strip()
                if not target:
                    continue
                base = target.rsplit("/", 1)[-1]
                key = normalize(base)
                if key in PLACEHOLDER_TARGETS:
                    skipped += 1
                    continue
                if key in index:
                    continue
                broken.append({
                    "src": str(f),
                    "line": lineno,
                    "raw": "[[" + inner + "]]",
                    "target": target,
                    "key": key,
                })
    return broken, skipped


def count_drafts(files: Sequence[Path]) -> List[str]:
    """frontmatter 里 maturity: draft 的页面（信息级，不算 issue）。"""
    drafts: List[str] = []
    for f in files:
        try:
            head = f.read_text(encoding="utf-8", errors="replace")[:600]
        except OSError:
            continue
        if re.search(r"^maturity:\s*draft\s*$", head, re.MULTILINE):
            drafts.append(str(f))
    return drafts


def _mimir_home() -> Path:
    """与运行时同一真源；import 失败退回环境变量/约定路径（CI 可用）。

    注意：本机 HOME 语义是双的（agent 沙箱里 HOME 就是 mimir home），
    所以不能直接 $HOME/.mimiraether，会双嵌套。见 RS19 同族修复。
    """
    try:
        from mimir_constants import get_mimir_home  # type: ignore

        return Path(get_mimir_home())
    except Exception:
        env = os.environ.get("MIMIR_AETHER_HOME") or os.environ.get("MIMIR_HOME")
        if env:
            return Path(env)
        home = Path.home()
        return _os_home() / ".mimiraether"


def _rel(paths: Sequence[str], wiki: Path, limit: int) -> List[str]:
    out: List[str] = []
    for p in list(paths)[:limit]:
        try:
            out.append(str(Path(p).relative_to(wiki)))
        except ValueError:
            out.append(str(p))
    return out


def render_report(wiki: Path, files: Sequence[Path], resolve_count: int, dups, cross, broken,
                  skipped_ph: int, drafts, present, missing,
                  elapsed_s: float, list_limit: int) -> Tuple[str, bool]:
    """返回 (报告文本, 是否有 issue)。报告首行是判定行 —— 它会被投递到飞书。"""
    ts = _dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    issues = bool(dups or broken)
    ph_note = (" · 例举占位符跳过 " + str(skipped_ph)) if skipped_ph else ""
    head = "[Wiki 质量门禁] " + ("⚠ 有真问题" if issues else "✅ 无问题") + " · " + ts
    lines = [
        head,
        "扫描: " + ",".join(present) + " · " + str(len(files)) + " 篇 .md"
        + "（解析面 " + str(resolve_count) + " 篇）· 跳过代码块与行内代码" + ph_note
        + " · 用时 " + ("%.2f" % elapsed_s) + "s",
    ]
    if missing:
        lines.append("未覆盖层（目录不存在，不是零问题）: " + ",".join(missing))
    if broken:
        lines.append("① 死链 " + str(len(broken)) + " 条:")
        for b in broken[:list_limit]:
            src = _rel([str(b["src"])], wiki, 1)[0]
            lines.append("   - " + src + ":" + str(b["line"]) + " → " + str(b["raw"]))
        if len(broken) > list_limit:
            lines.append("   …余 " + str(len(broken) - list_limit) + " 条（全量见 JSON）")
    if dups:
        lines.append("② 同页重复 " + str(len(dups)) + " 组（同目录、归一化后同名）:")
        for key, paths in dups[:list_limit]:
            lines.append("   - " + key + " → " + ", ".join(_rel(paths, wiki, 4)))
        if len(dups) > list_limit:
            lines.append("   …余 " + str(len(dups) - list_limit) + " 组")
    if cross:
        lines.append("   （信息级）同名跨目录 " + str(len(cross)) + " 组，未计入问题")
    if drafts:
        lines.append("③ 成熟度 draft 待晋级 " + str(len(drafts)) + " 篇（信息级）")
    lines.append("判定真源: repo scripts/wiki_quality_report.py（零 LLM）")
    return "\n".join(lines), issues


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Wiki 质量门禁报告层（零 LLM）")
    ap.add_argument("--wiki", default=None, help="wiki 根（默认 env WIKI_DIR 或 <os home>/wiki）")
    ap.add_argument("--paths", default="", help="逗号分隔的层名，覆盖默认策展层")
    ap.add_argument("--json", default="", help="机器可读结果落点（默认 data/ops/wiki_quality_last.json）")
    ap.add_argument("--list-limit", type=int, default=8)
    ap.add_argument("--strict", action="store_true", help="有 issue 时返回 1")
    ap.add_argument("--append-log", action="store_true", help="额外在 wiki/log.md 追加一行（默认不写）")
    args = ap.parse_args(argv)

    t0 = _dt.datetime.now()
    wiki = Path(args.wiki) if args.wiki else default_wiki()
    layers = tuple(x.strip() for x in args.paths.split(",") if x.strip()) or DEFAULT_LAYERS

    if not wiki.is_dir():
        print("[Wiki 质量门禁] ❌ 无法运行: wiki 目录不存在 " + str(wiki))
        return 2

    present, missing = _layer_summary(wiki, layers)
    files = _iter_md(wiki, layers)
    if not files:
        _dirs = ",".join(present) or "(无)"
        print("[Wiki 质量门禁] ❌ 无法运行: 策展层扫到 0 篇 .md（目录=" + _dirs
              + "）—— 这是仪表故障，不是「零问题」")
        return 2

    resolve_files = _iter_all_md(wiki)
    if not resolve_files:
        print("[Wiki 质量门禁] ❌ 无法运行: wiki 下扫不到任何 .md（解析面为空）")
        return 2

    index = build_index(resolve_files)
    dups, cross = find_duplicates(files, wiki)
    broken, skipped_ph = find_broken_links(files, index)
    drafts = count_drafts(files)
    elapsed = (_dt.datetime.now() - t0).total_seconds()

    text, issues = render_report(wiki, files, len(resolve_files), dups, cross, broken, skipped_ph,
                                 drafts, present, missing, elapsed, args.list_limit)
    print(text)

    if args.append_log:
        try:
            log = wiki / "log.md"
            with open(log, "a", encoding="utf-8") as fh:
                fh.write("- " + _dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S") + " — " + text.split("\n")[0] + "\n")
        except OSError as exc:
            print("(警告: log.md 追加失败 " + str(exc) + ")")

    out = Path(args.json) if args.json else (_mimir_home() / "data" / "ops" / "wiki_quality_last.json")
    try:
        out.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "ts": _dt.datetime.now().isoformat(timespec="seconds"),
            "wiki": str(wiki),
            "layers_present": present,
            "layers_missing": missing,
            "files_scanned": len(files),
            "broken_count": len(broken),
            "duplicate_groups": len(dups),
            "cross_dir_same_name": len(cross),
            "resolve_files": len(resolve_files),
            "placeholder_skipped": skipped_ph,
            "draft_count": len(drafts),
            "broken": broken[:200],
            "duplicates": [{"key": k, "paths": v} for k, v in dups[:50]],
            "elapsed_s": round(elapsed, 3),
            "exit_code": 1 if (issues and args.strict) else 0,
        }
        tmp = out.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, out)
    except OSError as exc:
        print("(警告: JSON 落点失败 " + str(exc) + ")")

    if issues and args.strict:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
