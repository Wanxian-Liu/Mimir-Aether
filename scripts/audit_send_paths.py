#!/usr/bin/env python3
"""audit_send_paths.py — 发件路径漂移自检（U4/D7 的可验证完成口径）

背景：D7 立项时 `~/.mimiraether/scripts/` 有多个一次性发件脚本各自硬编码收件箱路径，
其中 3 个指向已停更的 `~/.buzz-nostr/state/`（死路径）——「schema 漂移 + 路径漂移」的土壤。
本脚本把「已归一」变成可回归验证的口径，而不是一次性人工核查。

⚠️ 第一版用「行正则 + open( 同现」判定 → 漏掉 `INBOX = os.path.expanduser("...")` 这类
   变量赋值式硬编码（实测报 hardcoded=0，与 grep 9 个文件的盘上事实不符 = 假绿自检）。
   现改为 **AST 口径**：docstring 之外的字符串常量全量识别，不再依赖行内共现。

检查（只读）：
  A. 违规：代码里出现**非 canonical** 的 buzz-inbox 字面量（死路径 / /tmp / 相对路径）→ 退出码 1
  B. 提示：仍硬编码 canonical 路径（能跑但未走 buzz_send 单点）→ 计数报告，不阻塞
  C. 汇总：已委托 buzz_send 的脚本

用法：python3 audit_send_paths.py [--json] [--dir ~/.mimiraether/scripts]
"""
from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path

CANONICAL_MARKERS = ("/.openclaw/data/", "~/.openclaw/data/")
MAX_PATH_LEN = 160  # 超过视为报文正文（散文里提到路径不算路径用法）


def _classify(value: str) -> str | None:
    """返回 'canonical' / 'violation' / 'basename' / None(非路径样字面量)。

    路径样 = 含 'buzz-inbox' + 含 '/' + 长度 ≤ MAX_PATH_LEN + 无换行。
    文件名模板（f"buzz-inbox-{to}.jsonl"）无 '/' → 'basename'（目录来源由 canonical 常量唯一决定，
    不算漂移）；报文正文（长、含换行）→ None。
    """
    if "buzz-inbox" not in value:
        return None
    if "\n" in value or len(value) > MAX_PATH_LEN:
        return None
    if "/" not in value:
        return "basename"
    return "canonical" if any(m in value for m in CANONICAL_MARKERS) else "violation"


def _docstring_nodes(tree: ast.AST) -> set[int]:
    """收集模块/类/函数 docstring 的常量节点 id（这些是散文，不是路径用法）。"""
    out: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = getattr(node, "body", [])
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) \
                    and isinstance(body[0].value.value, str):
                out.add(id(body[0].value))
    return out


def scan_file(path: Path) -> dict:
    text = path.read_text(encoding="utf-8", errors="replace")
    try:
        tree = ast.parse(text)
    except SyntaxError as exc:
        return {"file": path.name, "error": f"SyntaxError: {exc}", "bad": [], "canonical": [],
                "delegated": False}
    skip = _docstring_nodes(tree)
    bad: list[dict] = []
    canonical: list[dict] = []
    basenames: list[dict] = []
    delegated = False
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and (node.module or "").endswith("buzz_send"):
            delegated = True
        if isinstance(node, ast.Import):
            if any(a.name.endswith("buzz_send") for a in node.names):
                delegated = True
        if isinstance(node, ast.Constant) and isinstance(node.value, str) \
                and id(node) not in skip:
            kind = _classify(node.value)
            rec = {"file": path.name, "line": node.lineno, "path": node.value[:90]}
            if kind == "canonical":
                canonical.append(rec)
            elif kind == "violation":
                bad.append(rec)
            elif kind == "basename":
                basenames.append(rec)
    return {"file": path.name, "bad": bad, "canonical": canonical, "basename": basenames,
            "delegated": delegated}



def scan(scripts_dir: Path) -> dict:
    files = []
    for path in sorted(scripts_dir.glob("*.py")):
        if ".bak" in path.name:
            continue
        files.append(scan_file(path))
    return {
        "violations": [b for f in files for b in f["bad"]],
        "hardcoded_canonical": [c for f in files for c in f["canonical"]],
        "basename_only": [b for f in files for b in f["basename"]],
        "delegated": [f["file"] for f in files if f["delegated"]],
        "errors": [{"file": f["file"], "error": f["error"]} for f in files if f.get("error")],
        "scanned": len(files),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="发件路径漂移自检（U4/D7）")
    ap.add_argument("--dir", default="/home/rayliu/.mimiraether/scripts")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    res = scan(Path(args.dir).expanduser())
    if args.json:
        print(json.dumps(res, ensure_ascii=False, indent=2))
    else:
        print(f"scan_dir={args.dir} scanned={res['scanned']} 解析失败={len(res['errors'])}")
        print(f"A. violations(非 canonical 字面量)={len(res['violations'])}")
        for v in res["violations"]:
            print(f"  [VIOLATION] {v['file']}:{v['line']} -> {v['path']}")
        print(f"B. hardcoded_canonical(路径正确但未走单点)={len(res['hardcoded_canonical'])}")
        for h in res["hardcoded_canonical"]:
            print(f"  · {h['file']}:{h['line']} -> {h['path']}")
        print(f"C. delegated(已委托 buzz_send)={len(res['delegated'])}: {', '.join(res['delegated']) or '-'}")
        print(f"D. basename_only(文件名模板，目录由 canonical 常量决定)={len(res['basename_only'])}")
        for b in res["basename_only"]:
            print(f"  · {b['file']}:{b['line']} -> {b['path']}")
        print("VERDICT:", "FAIL（存在死路径字面量）" if res["violations"] else "PASS（无死路径字面量）")
    return 1 if res["violations"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
