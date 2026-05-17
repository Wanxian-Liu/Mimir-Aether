"""
MimirCoreTool - 调用 Mimir-Core（泉）胶囊生成能力

Mimir-Core 是知识工厂：生成高质量胶囊。本模块为 MA 侧薄封装。

使用方式：
    MimirAether 发现有价值知识 → produce_capsule → GDI 评分 → 发布

Canonical 胶囊目录（HTML 真源）::
    ``{MIMIR_AETHER_HOME}/memory/capsules/*.html``
    见 ``docs/MIMIR_HTML_MEMORY_CONTRACT.md``。

``import mimicore`` 解析自 **git 仓库根** 下子模块 ``mimicore/``（``MIMIR_REPO_ROOT`` /
``git rev-parse`` / 相对本文件推断）。可选 ``MIMIR_CORE_ROOT`` 仅覆盖 **import 路径**，
不作为 ``public/*.md`` 发布目录。

工具注册模式（Hermes 对齐）: ``tools.registry.register()``
"""

from __future__ import annotations

import html
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from tools.registry import registry, tool_error, tool_result

_MIMICORE_IMPORT_DIR: Optional[Path] = None


def _resolve_repo_root() -> Path:
    """Git / 仓库根（源码与 mimicore 子模块）。"""
    env = os.environ.get("MIMIR_REPO_ROOT", "").strip()
    if env:
        return Path(os.path.expandvars(os.path.expanduser(env))).resolve()
    inferred = Path(__file__).resolve().parent.parent
    if (inferred / "mimicore").is_dir():
        return inferred
    try:
        proc = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            cwd=inferred,
            timeout=5,
            check=False,
        )
        if proc.returncode == 0 and proc.stdout.strip():
            root = Path(proc.stdout.strip()).resolve()
            if (root / "mimicore").is_dir():
                return root
    except (OSError, subprocess.SubprocessError):
        pass
    return inferred


def _resolve_mimicore_import_dir() -> Path:
    """mimicore 包目录（仅用于 sys.path / import，非胶囊发布路径）。"""
    global _MIMICORE_IMPORT_DIR
    if _MIMICORE_IMPORT_DIR is not None:
        return _MIMICORE_IMPORT_DIR

    mcr = os.environ.get("MIMIR_CORE_ROOT", "").strip()
    if mcr:
        candidate = Path(os.path.expandvars(os.path.expanduser(mcr))).resolve()
        if candidate.is_dir():
            _MIMICORE_IMPORT_DIR = candidate
            return candidate

    sub = _resolve_repo_root() / "mimicore"
    if sub.is_dir():
        _MIMICORE_IMPORT_DIR = sub
        return sub

    from mimir_constants import get_mimir_home

    fallback = get_mimir_home() / "mimicore"
    _MIMICORE_IMPORT_DIR = fallback
    return fallback


def _get_capsules_publish_dir() -> Path:
    """Canonical 胶囊发布目录（HTML）。"""
    from mimir_constants import get_mimir_home

    return get_mimir_home() / "memory" / "capsules"


def _ensure_mimircore_importable() -> None:
    """确保 mimicore 子模块可 import（仓库根子目录，与发布目录分离）。"""
    import_dir = str(_resolve_mimicore_import_dir())
    if import_dir not in sys.path:
        sys.path.insert(0, import_dir)


def _title_from_input(input_text: str) -> str:
    title = input_text.strip().split("\n")[0].strip()
    if title.startswith("#"):
        title = title.lstrip("#").strip()
    return title


def _title_slug(title: str) -> str:
    cleaned = re.sub(r"[^\w\u4e00-\u9fff\-]", "_", title)[:30]
    return cleaned[:20] if cleaned else "capsule"


def _capsule_publish_filename(capsule_id: str, title_slug: str) -> str:
    return f"{capsule_id[:12]}_{title_slug}.html"


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


def _publish_capsule_html(
    *,
    capsule: Any,
    capsule_id: str,
    input_text: str,
    gdi_value: float,
    capsule_type: str,
) -> str:
    """写入 memory/capsules/*.html；返回 publish_status 片段。"""
    publish_dir = _get_capsules_publish_dir()
    publish_dir.mkdir(parents=True, exist_ok=True)

    title = _title_from_input(input_text)
    title_slug = _title_slug(title)
    filename = _capsule_publish_filename(capsule_id, title_slug)
    filepath = publish_dir / filename

    extra: Dict[str, Any] = {"source": "MimirAether"}
    if hasattr(capsule, "taxonomy_tags") and capsule.taxonomy_tags:
        extra["tags"] = capsule.taxonomy_tags
    if hasattr(capsule, "knowledge_type") and capsule.knowledge_type:
        kt = capsule.knowledge_type
        if isinstance(kt, dict):
            extra["knowledge_type"] = kt.get("primary_type", "unknown")
            extra["confidence"] = kt.get("confidence", 0.5)

    cap_type_str = capsule_type
    if hasattr(capsule, "capsule_type") and capsule.capsule_type:
        cap_type_str = str(capsule.capsule_type)

    page = _build_capsule_html(
        capsule_id=capsule_id,
        title=title_slug,
        body_text=getattr(capsule, "content", "") or "",
        gdi_value=gdi_value,
        capsule_type=cap_type_str,
        extra_meta=extra,
    )
    filepath.write_text(page, encoding="utf-8")
    return f"published: {filename}"


def _meta_mimir_id_from_html(text: str) -> Optional[str]:
    m = re.search(
        r'<meta\s+name=["\']mimir-id["\']\s+content=["\']([^"\']+)["\']',
        text,
        re.IGNORECASE,
    )
    return m.group(1) if m else None


def _capsule_matches_id(capsule_file: Path, capsule_id: str) -> bool:
    if capsule_id in capsule_file.stem:
        return True
    try:
        head = capsule_file.read_text(encoding="utf-8")[:4096]
    except OSError:
        return False
    meta_id = _meta_mimir_id_from_html(head)
    if meta_id and (meta_id == capsule_id or capsule_id in meta_id):
        return True
    return capsule_id in head[:500]


# ─────────────────────────────────────────────────────────────
# 工具处理函数（返回 JSON 字符串，符合 Hermes 模式）
# ─────────────────────────────────────────────────────────────


def _handle_produce_capsule(
    input_text: str, capsule_type: str = "auto", auto_publish: bool = True
) -> str:
    _ensure_mimircore_importable()

    try:
        import sys as _sys

        for _mod_name in list(_sys.modules.keys()):
            if "mimicore" in _mod_name or "capsule_generator" in _mod_name:
                del _sys.modules[_mod_name]
        from mimicore.capsule_generator import CapsuleGenerator, CapsuleType

        type_map = {
            "auto": None,
            "innovate": CapsuleType.INNOVATE,
            "optimize": CapsuleType.OPTIMIZE,
            "repair": CapsuleType.REPAIR,
        }
        cap_type = type_map.get(capsule_type.lower(), None)

        generator = CapsuleGenerator()
        result = generator.generate_and_evaluate(
            input_text=input_text,
            capsule_type=cap_type,
            auto_publish=auto_publish,
            metadata={"source": "MimirAether", "capsule_type": capsule_type},
        )

        capsule = result.get("capsule")
        gdi_score = result.get("gdi_score")
        should_publish = result.get("should_publish", False)
        reason = result.get("reason", "")

        gdi_value = gdi_score.total if gdi_score else 0
        capsule_id = capsule.id if capsule else "unknown"

        publish_status = "not_published"
        if should_publish and auto_publish and capsule:
            try:
                publish_status = _publish_capsule_html(
                    capsule=capsule,
                    capsule_id=capsule_id,
                    input_text=input_text,
                    gdi_value=gdi_value,
                    capsule_type=capsule_type,
                )
            except Exception as save_err:
                publish_status = f"save_failed: {save_err}"
        elif should_publish and auto_publish:
            publish_status = "published"
        elif should_publish:
            publish_status = "pending_publish"

        return tool_result(
            capsule_id=capsule_id,
            gdi_score=gdi_value,
            reason=reason,
            publish_status=publish_status,
            should_publish=should_publish,
        )

    except ImportError as e:
        return tool_error(f"Cannot import Mimir-Core module: {e}")
    except Exception as e:
        return tool_error(f"{type(e).__name__}: {str(e)}")


def _dynamic_produce_handler(args, **kwargs):
    import importlib as _importlib
    import sys as _sys

    for _mod_name in list(_sys.modules.keys()):
        if "mimicore" in _mod_name or "capsule_generator" in _mod_name:
            del _sys.modules[_mod_name]

    import tools.mimircore_tool as _mt

    _importlib.reload(_mt)

    return _mt._handle_produce_capsule(
        input_text=args.get("input_text", ""),
        capsule_type=args.get("capsule_type", "auto"),
        auto_publish=args.get("auto_publish", True),
    )


def _handle_get_capsule_by_id(capsule_id: str) -> str:
    try:
        capsules_dir = _get_capsules_publish_dir()
        if not capsules_dir.is_dir():
            return tool_error(f"Capsule not found: {capsule_id}")

        for capsule_file in sorted(capsules_dir.glob("*.html")):
            if _capsule_matches_id(capsule_file, capsule_id):
                content = capsule_file.read_text(encoding="utf-8")
                return tool_result(
                    capsule_id=capsule_id,
                    file=capsule_file.name,
                    content_preview=content[:1000],
                )

        return tool_error(f"Capsule not found: {capsule_id}")

    except Exception as e:
        return tool_error(f"{type(e).__name__}: {str(e)}")


def _handle_list_capsules(tag_filter: str = None, limit: int = 20) -> str:
    try:
        capsules_dir = _get_capsules_publish_dir()
        capsules_dir.mkdir(parents=True, exist_ok=True)
        capsules = sorted(
            capsules_dir.glob("*.html"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )

        if tag_filter:
            capsules = [
                c
                for c in capsules
                if tag_filter.lower() in c.stem.lower()
                or tag_filter.lower() in c.read_text(encoding="utf-8")[:2000].lower()
            ]

        total = len(capsules)
        capsules = capsules[:limit]

        items = [
            {
                "name": c.stem,
                "modified": time.strftime(
                    "%Y-%m-%d", time.localtime(c.stat().st_mtime)
                ),
            }
            for c in capsules
        ]

        return tool_result(total=total, shown=len(items), capsules=items)

    except Exception as e:
        return tool_error(f"{type(e).__name__}: {str(e)}")


def _handle_improve_capsule(capsule_id: str, improvement_hint: str) -> str:
    try:
        capsule_detail = _handle_get_capsule_by_id(capsule_id)
        improved_text = f"{capsule_detail}\n\n[改进要求]: {improvement_hint}"
        return _handle_produce_capsule(
            improved_text, capsule_type="optimize", auto_publish=True
        )

    except Exception as e:
        return tool_error(f"{type(e).__name__}: {str(e)}")


# ─────────────────────────────────────────────────────────────
# 注册所有 MimirCore 工具到 registry（Hermes 模式）
# ─────────────────────────────────────────────────────────────

registry.register(
    name="produce_capsule",
    toolset="mimircore",
    schema={
        "name": "produce_capsule",
        "description": "调用Mimir-Core生成胶囊。Mimir-Core是MimirAether的知识工厂，负责生成高质量胶囊。输入知识内容，输出评分≥70的胶囊。",
        "parameters": {
            "type": "object",
            "properties": {
                "input_text": {
                    "type": "string",
                    "description": "要生成胶囊的知识内容（可以是技术文档、经验总结、解决方案等）",
                },
                "capsule_type": {
                    "type": "string",
                    "description": "胶囊类型",
                    "enum": ["auto", "innovate", "optimize", "repair"],
                    "default": "auto",
                },
                "auto_publish": {
                    "type": "boolean",
                    "description": "是否自动发布（GDI≥70时）",
                    "default": True,
                },
            },
            "required": ["input_text"],
        },
    },
    handler=_dynamic_produce_handler,
    emoji="💊",
    description="Generate high-quality knowledge capsules via Mimir-Core",
)

registry.register(
    name="get_capsule_by_id",
    toolset="mimircore",
    schema={
        "name": "get_capsule_by_id",
        "description": "根据ID获取胶囊详情",
        "parameters": {
            "type": "object",
            "properties": {
                "capsule_id": {
                    "type": "string",
                    "description": "胶囊ID",
                }
            },
            "required": ["capsule_id"],
        },
    },
    handler=lambda args, **kw: _handle_get_capsule_by_id(
        capsule_id=args.get("capsule_id", ""),
    ),
    emoji="📦",
    description="Get capsule details by ID",
)

registry.register(
    name="list_capsules",
    toolset="mimircore",
    schema={
        "name": "list_capsules",
        "description": "列出所有胶囊",
        "parameters": {
            "type": "object",
            "properties": {
                "tag_filter": {
                    "type": "string",
                    "description": "标签过滤（可选）",
                },
                "limit": {
                    "type": "integer",
                    "description": "返回数量限制",
                    "default": 20,
                },
            },
        },
    },
    handler=lambda args, **kw: _handle_list_capsules(
        tag_filter=args.get("tag_filter"),
        limit=args.get("limit", 20),
    ),
    emoji="📋",
    description="List all capsules with optional tag filter",
)

registry.register(
    name="improve_capsule",
    toolset="mimircore",
    schema={
        "name": "improve_capsule",
        "description": "改进现有胶囊",
        "parameters": {
            "type": "object",
            "properties": {
                "capsule_id": {
                    "type": "string",
                    "description": "要改进的胶囊ID",
                },
                "improvement_hint": {
                    "type": "string",
                    "description": "改进提示",
                },
            },
            "required": ["capsule_id", "improvement_hint"],
        },
    },
    handler=lambda args, **kw: _handle_improve_capsule(
        capsule_id=args.get("capsule_id", ""),
        improvement_hint=args.get("improvement_hint", ""),
    ),
    emoji="🔧",
    description="Improve an existing capsule with hints",
)


# ─────────────────────────────────────────────────────────────
# 向后兼容层（旧代码仍可调用）
# ─────────────────────────────────────────────────────────────

TOOL_FUNCTIONS = {
    "produce_capsule": _handle_produce_capsule,
    "get_capsule_by_id": _handle_get_capsule_by_id,
    "list_capsules": _handle_list_capsules,
    "improve_capsule": _handle_improve_capsule,
}

TOOL_SCHEMAS = {
    name: entry.schema.get("parameters", {})
    for name, entry in registry._tools.items()
    if entry.toolset == "mimircore"
}


def get_tool_functions() -> Dict[str, callable]:
    """获取所有工具函数（向后兼容）"""
    return TOOL_FUNCTIONS
