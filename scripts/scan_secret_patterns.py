#!/usr/bin/env python3
"""密钥/PII 模式扫描器（T95 会后 PII 第 3 项定性 · 复核用可跑判据）

口径真源 = `agent/memory_fence.py::MemoryFence.SENSITIVE_PATTERNS`（我域唯一密钥/PII 模式表）。
输出：逐条命中 `file:line  pattern_type  severity  shape(掩码)` + 末行 `TOTAL=<n> KEY_CLASS=<m>`。
**永不打印完整命中值**：只印前 4 + 后 2 字符并标长度。

用法：
  scan_secret_patterns.py <file> [--json]
  scan_secret_patterns.py --selftest      # 正控 1 条 / 负控 1 条（正负双向）
rc: 0 = 扫描完成（与命中数无关）· 2 = 参数/读文件错 · selftest: 0 = 双控通过
"""
from __future__ import annotations
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agent.memory_fence import MemoryFence  # noqa: E402

KEY_CLASS = {
    "openai_key", "anthropic_key", "aws_access_key", "aws_secret_key", "github_token",
    "slack_token", "stripe_key", "generic_secret", "jwt_token", "bearer_token",
}


def mask(v: str) -> str:
    return f"{v[:4]}…{v[-2:]}(len={len(v)})" if len(v) > 10 else "***"


def scan_text(text: str) -> list[dict]:
    out = []
    for name, info in MemoryFence.SENSITIVE_PATTERNS.items():
        rx = re.compile(info["pattern"])
        for m in rx.finditer(text):
            out.append({
                "line": text[: m.start()].count("\n") + 1,
                "type": name,
                "severity": info.get("severity", "?"),
                "key_class": name in KEY_CLASS,
                "shape": mask(m.group(0)),
            })
    out.sort(key=lambda r: (r["line"], r["type"]))
    return out


def main(argv: list[str]) -> int:
    if "--selftest" in argv:
        # 正控：合成假值（AWS secret 形态 40 字符）必须被计数
        pos = scan_text('x = "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEYY"\n')
        # 负控：纯占位/中文描述必须为 0
        neg = scan_text("token 类型为 gho_*（占位描述）· SSH 指纹见附表\n")
        ok = bool(pos) and not neg
        print(f"selftest 正控命中={len(pos)} 负控命中={len(neg)} -> {'OK' if ok else 'FAIL'}")
        return 0 if ok else 1
    if not argv or argv[0].startswith("-"):
        print(__doc__)
        return 2
    p = Path(argv[0]).expanduser()
    try:
        text = p.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        print(f"ERR read {p}: {exc}")
        return 2
    rows = scan_text(text)
    if "--json" in argv:
        print(json.dumps(rows, ensure_ascii=False, indent=1))
    else:
        for r in rows:
            print(f"{p.name}:{r['line']}\t{r['type']}\t{r['severity']}\t{r['shape']}")
    key_hits = sum(1 for r in rows if r["key_class"])
    print(f"TOTAL={len(rows)} KEY_CLASS={key_hits}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
