#!/usr/bin/env python3
"""一次性迁移脚本：mimicore/public/*.md → memory/capsules/*.html

调用 _build_capsule_html() 生成符合 MIMIR_HTML_MEMORY_CONTRACT.md 规范的 HTML。
"""

import hashlib
import html
import json
import os
import re
import sys
import time
import yaml
from pathlib import Path
from typing import Any, Dict, List, Optional

# ── 路径 ──────────────────────────────────────────────
REPO_ROOT = Path(__file__).resolve().parent.parent
PUBLIC_DIR = REPO_ROOT / "mimicore" / "public"
MIMIR_HOME = Path(os.environ.get("MIMIR_AETHER_HOME", os.path.expanduser("~/.mimiraether")))
CAPSULES_DIR = MIMIR_HOME / "memory" / "capsules"


# ── 从 mimircore_tool.py 复制的核心函数（避免 import 副作用） ──

def _build_capsule_html(
    *,
    capsule_id: str,
    title: str,
    body_text: str,
    gdi_value: float,
    capsule_type: str,
    extra_meta: Optional[Dict[str, Any]] = None,
) -> str:
    """最小 HTML 契约页（docs/MIMIR_HTML_MEMORY_CONTRACT.md §3.3）。"""
    created = time.strftime("%Y-%m-%dT%H:%M:%S+08:00")
    safe_title = html.escape(title)
    safe_body = html.escape(body_text or "")
    meta_rows: List[str] = [
        f'<dt>GDI</dt><dd>{html.escape(str(round(gdi_value, 2)))}</dd>',
        f'<dt>capsule_type</dt><dd>{html.escape(capsule_type)}</dd>',
    ]
    if extra_meta:
        for key, val in extra_meta.items():
            if val is None:
                continue
            if isinstance(val, (list, dict)):
                val_str = json.dumps(val, ensure_ascii=False)
            else:
                val_str = str(val)
            meta_rows.append(
                f"<dt>{html.escape(str(key))}</dt><dd>{html.escape(val_str)}</dd>"
            )

    return (
        "<!DOCTYPE html>\n"
        '<html lang="zh-CN">\n'
        "<head>\n"
        '<meta charset="utf-8">\n'
        f"<title>{safe_title}</title>\n"
        '<meta name="mimir-kind" content="capsule">\n'
        f'<meta name="mimir-id" content="{html.escape(capsule_id)}">\n'
        f'<meta name="mimir-created" content="{created}">\n'
        f'<meta name="mimir-updated" content="{created}">\n'
        '<meta name="mimir-source" content="MimirAether">\n'
        "</head>\n"
        "<body>\n"
        f"<h1>{safe_title}</h1>\n"
        f"<dl>\n{''.join(meta_rows)}\n</dl>\n"
        f'<article><pre style="white-space:pre-wrap">{safe_body}</pre></article>\n'
        "</body>\n"
        "</html>\n"
    )


def _title_slug(title: str) -> str:
    cleaned = re.sub(r"[^\w\u4e00-\u9fff\-]", "_", title)[:30]
    return cleaned[:20] if cleaned else "capsule"


def _capsule_publish_filename(capsule_id: str, title_slug: str) -> str:
    return f"{capsule_id[:12]}_{title_slug}.html"


def _generate_capsule_id(title: str, body: str) -> str:
    """为没有 capsule_id 的旧胶囊生成一个。"""
    h = hashlib.sha256(f"{title}{body[:500]}".encode()).hexdigest()[:12]
    return h


# ── 主流程 ──

def parse_md_file(filepath: Path) -> Optional[Dict[str, Any]]:
    """解析 .md 文件，返回 {capsule_id, title, body, gdi, type, extra} 或 None。"""
    text = filepath.read_text(encoding="utf-8")

    # 解析 YAML frontmatter
    fm: Dict[str, Any] = {}
    body = text
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            try:
                fm = yaml.safe_load(parts[1]) or {}
            except yaml.YAMLError:
                pass
            body = parts[2].strip()

    capsule_id = fm.get("capsule_id") or _generate_capsule_id(
        fm.get("title", filepath.stem), body
    )
    title = fm.get("title", filepath.stem)
    gdi = float(fm.get("gdi", 0.5))
    cap_type = fm.get("capsule_type", "unknown")

    # extra_meta: 保留 source, tags, category 等非核心字段
    extra: Dict[str, Any] = {}
    for key in ("source", "tags", "category", "status", "created", "imported_at"):
        if key in fm and fm[key] is not None:
            extra[key] = fm[key]

    return {
        "capsule_id": capsule_id,
        "title": title,
        "body": body,
        "gdi": gdi,
        "type": cap_type,
        "extra": extra,
        "path": filepath,
    }


def main():
    md_files = sorted(PUBLIC_DIR.glob("*.md"))
    print(f"Found {len(md_files)} .md files in {PUBLIC_DIR}")

    CAPSULES_DIR.mkdir(parents=True, exist_ok=True)

    ok = 0
    skip = 0
    fail = 0

    for fp in md_files:
        try:
            data = parse_md_file(fp)
            if data is None:
                skip += 1
                continue

            slug = _title_slug(data["title"])
            filename = _capsule_publish_filename(data["capsule_id"], slug)
            out_path = CAPSULES_DIR / filename

            if out_path.exists():
                skip += 1
                continue

            html_content = _build_capsule_html(
                capsule_id=data["capsule_id"],
                title=data["title"],
                body_text=data["body"],
                gdi_value=data["gdi"],
                capsule_type=data["type"],
                extra_meta=data["extra"] if data["extra"] else None,
            )

            out_path.write_text(html_content, encoding="utf-8")
            ok += 1
        except Exception as e:
            print(f"FAIL: {fp.name} — {e}", file=sys.stderr)
            fail += 1

    print(f"\nDone: {ok} migrated, {skip} skipped, {fail} failed")
    print(f"Output: {CAPSULES_DIR}")


if __name__ == "__main__":
    main()
