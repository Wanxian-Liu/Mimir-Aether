"""
MimirAether Context References - @引用模式解析

学习自Hermes context_references.py设计。

核心功能：
- 解析@diff, @staged, @file, @folder, @git, @url引用
- 敏感路径过滤
- 引用内容扩展
"""

from __future__ import annotations

import re
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, List, Callable, Awaitable

# ============================================================================
# 常量
# ============================================================================

# 引用模式正则
_QUOTED_REFERENCE_VALUE = r'(?:`[^`\n]+`|"[^"\n]+"|\'[^\'\n]+\')'
REFERENCE_PATTERN = re.compile(
    rf"(?<![\w/])@(?:(?P<simple>diff|staged)\b|(?P<kind>file|folder|git|url):(?P<value>{_QUOTED_REFERENCE_VALUE}(?::\d+(?:-\d+)?)?|\S+))"
)

# 敏感目录
_SENSITIVE_HOME_DIRS = (".ssh", ".aws", ".gnupg", ".kube", ".docker", ".azure", ".config/gh")

# 敏感文件
_SENSITIVE_HOME_FILES = (
    ".ssh/authorized_keys",
    ".ssh/id_rsa",
    ".ssh/id_ed25519",
    ".ssh/config",
    ".bashrc",
    ".zshrc",
    ".profile",
    ".bash_profile",
    ".netrc",
    ".pgpass",
    ".npmrc",
    ".pypirc",
)

# Subdirectories under ~/.hermes that must not be attached via @file/@folder.
_SENSITIVE_HERMES_DIRS: tuple[str, ...] = ()


# ============================================================================
# 数据类
# ============================================================================

@dataclass(frozen=True)
class ContextReference:
    """单个上下文引用"""
    raw: str           # 原始匹配文本
    kind: str          # 引用类型：diff, staged, file, folder, git, url
    target: str        # 引用目标
    start: int         # 在原消息中的起始位置
    end: int           # 在原消息中的结束位置
    line_start: Optional[int] = None  # 行号范围起始
    line_end: Optional[int] = None    # 行号范围结束


@dataclass
class ContextReferenceResult:
    """引用解析结果"""
    message: str                          # 处理后的消息
    original_message: str                 # 原始消息
    references: List[ContextReference] = field(default_factory=list)  # 解析出的引用
    warnings: List[str] = field(default_factory=list)  # 警告信息
    injected_tokens: int = 0              # 注入的token数估算
    expanded: bool = False                # 是否成功扩展
    blocked: bool = False                # 是否被阻止


# ============================================================================
# 工具函数
# ============================================================================

def _is_sensitive_path(path: Path) -> bool:
    """检查路径是否敏感"""
    path_str = str(path)
    
    # 检查敏感目录
    parts = path.parts
    for sensitive in _SENSITIVE_HOME_DIRS:
        if sensitive in parts:
            return True
    
    # 检查敏感文件
    for sensitive in _SENSITIVE_HOME_FILES:
        if path_str.endswith(sensitive) or f"/{sensitive}" in path_str:
            return True
    
    return False


def _estimate_tokens(text: str) -> int:
    """估算token数（简单方法：字符数/4）"""
    return len(text) // 4


def _read_file_safe(path: Path, max_lines: int = 1000) -> Optional[str]:
    """安全读取文件内容"""
    try:
        if not path.exists():
            return None
        if not path.is_file():
            return None
        if _is_sensitive_path(path):
            return None
        
        with open(path, 'r', encoding='utf-8') as f:
            lines = []
            for i, line in enumerate(f):
                if i >= max_lines:
                    lines.append(f"... (truncated, {max_lines}+ lines)")
                    break
                lines.append(line.rstrip())
            return "\n".join(lines)
    except (PermissionError, OSError):
        return None


# ============================================================================
# 引用解析
# ============================================================================

def parse_context_references(message: str) -> List[ContextReference]:
    """
    从消息中解析@引用

    支持的类型：
    - @diff: git diff
    - @staged: git staged changes
    - @file: 文件内容
    - @folder: 文件夹内容
    - @git: git信息
    - @url: URL内容

    Args:
        message: 用户消息

    Returns:
        解析出的引用列表
    """
    refs: List[ContextReference] = []
    if not message:
        return refs

    for match in REFERENCE_PATTERN.finditer(message):
        simple = match.group("simple")
        if simple:
            # 简单引用：@diff, @staged
            refs.append(ContextReference(
                raw=match.group(0),
                kind=simple,
                target="",
                start=match.start(),
                end=match.end(),
            ))
            continue

        # 复杂引用：@file:xxx, @folder:xxx, @git:xxx, @url:xxx
        kind = match.group("kind")
        value = match.group("value") or ""
        
        # 处理行号范围
        line_start = None
        line_end = None
        target = value

        if kind == "file" and ":" in value:
            # file:path:lineStart-lineEnd
            path_part, line_part = value.rsplit(":", 1)
            target = path_part
            if "-" in line_part:
                parts = line_part.split("-", 1)
                line_start = int(parts[0])
                line_end = int(parts[1]) if len(parts) > 1 else line_start
            else:
                line_start = int(line_part)
                line_end = line_start

        refs.append(ContextReference(
            raw=match.group(0),
            kind=kind,
            target=target,
            start=match.start(),
            end=match.end(),
            line_start=line_start,
            line_end=line_end,
        ))

    return refs


def _remove_reference_tokens(message: str, refs: List[ContextReference]) -> str:
    """从消息中移除@引用标记"""
    result = message
    # 从后向前替换，避免位置偏移
    for ref in sorted(refs, key=lambda r: r.start, reverse=True):
        result = result[:ref.start] + result[ref.end:]
    return result


# ============================================================================
# 引用扩展
# ============================================================================

async def _expand_reference_async(
    ref: ContextReference,
    cwd: Path,
    url_fetcher: Optional[Callable[[str], Awaitable[str]]] = None,
) -> tuple[Optional[str], Optional[str]]:
    """
    异步扩展单个引用

    Returns:
        (warning, block_content) - warning或content
    """
    warning = None
    block = None

    if ref.kind == "diff":
        # git diff
        import subprocess
        try:
            result = subprocess.run(
                ["git", "diff"],
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=10
            )
            block = f"```git diff\n{result.stdout[:5000]}\n```"
        except Exception as e:
            warning = f"git diff failed: {e}"

    elif ref.kind == "staged":
        # git diff --staged
        import subprocess
        try:
            result = subprocess.run(
                ["git", "diff", "--staged"],
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=10
            )
            block = f"```git diff --staged\n{result.stdout[:5000]}\n```"
        except Exception as e:
            warning = f"git diff --staged failed: {e}"

    elif ref.kind == "file":
        # 文件内容
        file_path = cwd / ref.target if not os.path.isabs(ref.target) else Path(ref.target)
        file_path = file_path.expanduser().resolve()

        if _is_sensitive_path(file_path):
            warning = f"Access to sensitive path denied: {ref.target}"
        elif not file_path.exists():
            warning = f"File not found: {ref.target}"
        else:
            content = _read_file_safe(file_path)
            if content is None:
                warning = f"Cannot read file: {ref.target}"
            else:
                # 应用行号范围
                if ref.line_start:
                    lines = content.split("\n")
                    start = max(0, ref.line_start - 1)
                    end = min(len(lines), ref.line_end or ref.line_start)
                    content = "\n".join(lines[start:end])
                
                block = f"```{ref.target}\n{content[:5000]}\n```"

    elif ref.kind == "folder":
        # 文件夹内容
        folder_path = cwd / ref.target if not os.path.isabs(ref.target) else Path(ref.target)
        folder_path = folder_path.expanduser().resolve()

        if _is_sensitive_path(folder_path):
            warning = f"Access to sensitive folder denied: {ref.target}"
        elif not folder_path.exists():
            warning = f"Folder not found: {ref.target}"
        elif not folder_path.is_dir():
            warning = f"Not a directory: {ref.target}"
        else:
            try:
                items = []
                for item in sorted(folder_path.iterdir())[:50]:
                    items.append(f"{item.name}/" if item.is_dir() else item.name)
                block = f"```\n{ref.target}/\n" + "\n".join(items[:50]) + "\n```"
            except Exception as e:
                warning = f"Cannot list folder: {e}"

    elif ref.kind == "git":
        # git status
        import subprocess
        try:
            result = subprocess.run(
                ["git", "status", "--short"],
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=10
            )
            block = f"```git status\n{result.stdout[:2000]}\n```"
        except Exception as e:
            warning = f"git status failed: {e}"

    elif ref.kind == "url":
        # URL内容
        if url_fetcher:
            try:
                content = await url_fetcher(ref.target)
                block = f"```\n{ref.target}\n{content[:5000]}\n```"
            except Exception as e:
                warning = f"URL fetch failed: {e}"
        else:
            warning = f"URL fetching not configured: {ref.target}"

    return warning, block


def _expand_reference(
    ref: ContextReference,
    cwd: Path,
    url_fetcher: Optional[Callable[[str], str]] = None,
) -> tuple[Optional[str], Optional[str]]:
    """同步版本的引用扩展"""
    warning = None
    block = None

    if ref.kind == "diff":
        import subprocess
        try:
            result = subprocess.run(
                ["git", "diff"],
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=10
            )
            block = f"```git diff\n{result.stdout[:5000]}\n```"
        except Exception as e:
            warning = f"git diff failed: {e}"

    elif ref.kind == "staged":
        import subprocess
        try:
            result = subprocess.run(
                ["git", "diff", "--staged"],
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=10
            )
            block = f"```git diff --staged\n{result.stdout[:5000]}\n```"
        except Exception as e:
            warning = f"git diff --staged failed: {e}"

    elif ref.kind == "file":
        target = os.path.expanduser(ref.target)
        file_path = cwd / target if not os.path.isabs(target) else Path(target)
        file_path = file_path.resolve()

        if _is_sensitive_path(file_path):
            warning = f"Access to sensitive path denied: {ref.target}"
        elif not file_path.exists():
            warning = f"File not found: {ref.target}"
        else:
            content = _read_file_safe(file_path)
            if content is None:
                warning = f"Cannot read file: {ref.target}"
            else:
                if ref.line_start:
                    lines = content.split("\n")
                    start = max(0, ref.line_start - 1)
                    end = min(len(lines), ref.line_end or ref.line_start)
                    content = "\n".join(lines[start:end])
                block = f"```{ref.target}\n{content[:5000]}\n```"

    elif ref.kind == "folder":
        target = os.path.expanduser(ref.target)
        folder_path = cwd / target if not os.path.isabs(target) else Path(target)
        folder_path = folder_path.resolve()

        if _is_sensitive_path(folder_path):
            warning = f"Access to sensitive folder denied: {ref.target}"
        elif not folder_path.exists():
            warning = f"Folder not found: {ref.target}"
        elif not folder_path.is_dir():
            warning = f"Not a directory: {ref.target}"
        else:
            try:
                items = []
                for item in sorted(folder_path.iterdir())[:50]:
                    items.append(f"{item.name}/" if item.is_dir() else item.name)
                block = f"```\n{ref.target}/\n" + "\n".join(items[:50]) + "\n```"
            except Exception as e:
                warning = f"Cannot list folder: {e}"

    elif ref.kind == "git":
        import subprocess
        try:
            result = subprocess.run(
                ["git", "status", "--short"],
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=10
            )
            block = f"```git status\n{result.stdout[:2000]}\n```"
        except Exception as e:
            warning = f"git status failed: {e}"

    elif ref.kind == "url":
        if url_fetcher:
            try:
                content = url_fetcher(ref.target)
                block = f"```\n{ref.target}\n{content[:5000]}\n```"
            except Exception as e:
                warning = f"URL fetch failed: {e}"
        else:
            warning = f"URL fetching not configured: {ref.target}"

    return warning, block


# ============================================================================
# Hermès兼容辅助函数
# ============================================================================


def _parse_file_reference_value(value: str) -> tuple[str, int | None, int | None]:
    """解析文件引用值，支持带行号范围的格式（Hermès兼容）"""
    import re
    quoted_match = re.match(
        r'^(?P<quote>`|"|\')(?P<path>.+?)(?P=quote)(?::(?P<start>\d+)(?:-(?P<end>\d+))?)?$',
        value,
    )
    if quoted_match:
        line_start = quoted_match.group("start")
        line_end = quoted_match.group("end")
        return (
            quoted_match.group("path"),
            int(line_start) if line_start is not None else None,
            int(line_end or line_start) if line_start is not None else None,
        )
    range_match = re.match(r"^(?P<path>.+?):(?P<start>\d+)(?:-(?P<end>\d+))?$", value)
    if range_match:
        line_start = int(range_match.group("start"))
        return (
            range_match.group("path"),
            line_start,
            int(range_match.group("end") or range_match.group("start")),
        )
    return _strip_reference_wrappers(value), None, None


def _resolve_path(cwd: Path, target: str, *, allowed_root: Path | None = None) -> Path:
    """解析引用路径，支持allowed_root限制（Hermès兼容）"""
    path = Path(os.path.expanduser(target))
    if not path.is_absolute():
        path = cwd / path
    resolved = path.resolve()
    if allowed_root is not None:
        try:
            resolved.relative_to(allowed_root)
        except ValueError as exc:
            raise ValueError("path is outside the allowed workspace") from exc
    return resolved


def _ensure_reference_path_allowed(path: Path) -> None:
    """确保引用路径不在敏感区域内（Hermès兼容）"""
    # 自研: 用Path替代
    home = Path(os.path.expanduser("~")).resolve()
    hermes_home = Path.home() / ".hermes".resolve()

    blocked_exact = {home / rel for rel in _SENSITIVE_HOME_FILES}
    blocked_exact.add(hermes_home / ".env")
    blocked_dirs = [home / rel for rel in _SENSITIVE_HOME_DIRS]
    blocked_dirs.extend(hermes_home / rel for rel in _SENSITIVE_HERMES_DIRS)

    if path in blocked_exact:
        raise ValueError("path is a sensitive credential file and cannot be attached")

    for blocked_dir in blocked_dirs:
        try:
            path.relative_to(blocked_dir)
            raise ValueError(f"path is inside a protected directory and cannot be attached: {blocked_dir}")
        except ValueError:
            pass


def _expand_file_reference(
    ref: ContextReference,
    cwd: Path,
    *,
    allowed_root: Path | None = None,
) -> tuple[str | None, str | None]:
    """展开文件引用为代码块（Hermès兼容）"""
    path = _resolve_path(cwd, ref.target, allowed_root=allowed_root)
    _ensure_reference_path_allowed(path)
    if not path.exists():
        return f"{ref.raw}: file not found", None
    if not path.is_file():
        return f"{ref.raw}: path is not a file", None
    if _is_binary_file(path):
        return f"{ref.raw}: binary files are not supported", None

    text = path.read_text(encoding="utf-8")
    if ref.line_start is not None:
        lines = text.splitlines()
        start_idx = max(ref.line_start - 1, 0)
        end_idx = min(ref.line_end or ref.line_start, len(lines))
        text = "\n".join(lines[start_idx:end_idx])

    lang = _code_fence_language(path)
    label = ref.raw
    return None, f"📄 {label} ({_estimate_tokens(text)} tokens)\n```{lang}\n{text}\n```"


def _expand_folder_reference(
    ref: ContextReference,
    cwd: Path,
    *,
    allowed_root: Path | None = None,
) -> tuple[str | None, str | None]:
    """展开文件夹引用为列表（Hermès兼容）"""
    path = _resolve_path(cwd, ref.target, allowed_root=allowed_root)
    _ensure_reference_path_allowed(path)
    if not path.exists():
        return f"{ref.raw}: folder not found", None
    if not path.is_dir():
        return f"{ref.raw}: path is not a folder", None

    listing = _build_folder_listing(path, cwd)
    return None, f"📁 {ref.raw} ({_estimate_tokens(listing)} tokens)\n{listing}"


def _expand_git_reference(
    ref: ContextReference,
    cwd: Path,
    args: list[str],
    label: str,
) -> tuple[str | None, str | None]:
    """展开git引用为diff/log内容（Hermès兼容）"""
    import subprocess
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=30,
        )
    except subprocess.TimeoutExpired:
        return f"{ref.raw}: git command timed out (30s)", None
    if result.returncode != 0:
        stderr = (result.stderr or "").strip() or "git command failed"
        return f"{ref.raw}: {stderr}", None
    content = result.stdout.strip()
    if not content:
        content = "(no output)"
    return None, f"🧾 {label} ({_estimate_tokens(content)} tokens)\n```diff\n{content}\n```"


async def _fetch_url_content(
    url: str,
    *,
    url_fetcher: Callable | None = None,
) -> str:
    """异步获取URL内容（Hermès兼容）"""
    import inspect
    if url_fetcher is None:
        url_fetcher = _default_url_fetcher
    content = url_fetcher(url)
    if inspect.isawaitable(content):
        content = await content
    return str(content or "").strip()


async def _default_url_fetcher(url: str) -> str:
    """默认URL fetcher（Hermès兼容，桩实现）"""
    # MimirAether简化实现：暂不支持默认URL抓取
    return ""


async def preprocess_context_references_async(
    message: str,
    *,
    cwd: str | Path,
    context_length: int,
    url_fetcher: Callable | None = None,
    allowed_root: str | Path | None = None,
) -> ContextReferenceResult:
    """异步预处理上下文引用（Hermès兼容）"""
    refs = parse_context_references(message)
    if not refs:
        return ContextReferenceResult(message=message, original_message=message)

    cwd_path = Path(cwd).expanduser().resolve()
    allowed_root_path = (
        Path(allowed_root).expanduser().resolve() if allowed_root is not None else cwd_path
    )
    warnings: list[str] = []
    blocks: list[str] = []
    injected_tokens = 0

    for ref in refs:
        warning, block = await _expand_reference_async(
            ref,
            cwd_path,
            url_fetcher=url_fetcher,
        )
        if warning:
            warnings.append(warning)
        if block:
            blocks.append(block)
            injected_tokens += _estimate_tokens(block)

    hard_limit = max(1, int(context_length * 0.50))
    soft_limit = max(1, int(context_length * 0.25))
    if injected_tokens > hard_limit:
        warnings.append(
            f"@ context injection refused: {injected_tokens} tokens exceeds the 50% hard limit ({hard_limit})."
        )
        return ContextReferenceResult(
            message=message,
            original_message=message,
            references=refs,
            warnings=warnings,
            injected_tokens=injected_tokens,
            expanded=False,
            blocked=True,
        )

    if injected_tokens > soft_limit:
        warnings.append(
            f"@ context injection warning: {injected_tokens} tokens exceeds the 25% soft limit ({soft_limit})."
        )

    stripped = _remove_reference_tokens(message, refs)
    final = stripped
    if warnings:
        final = f"{final}\n\n--- Context Warnings ---\n" + "\n".join(f"- {w}" for w in warnings)
    if blocks:
        final = f"{final}\n\n--- Attached Context ---\n\n" + "\n\n".join(blocks)

    return ContextReferenceResult(
        message=final.strip(),
        original_message=message,
        references=refs,
        warnings=warnings,
        injected_tokens=injected_tokens,
        expanded=bool(blocks or warnings),
        blocked=False,
    )


# ============================================================================
# 主处理函数
# ============================================================================

def preprocess_context_references(
    message: str,
    *,
    cwd: str | Path,
    context_length: int = 128000,
    url_fetcher: Optional[Callable[[str], str]] = None,
) -> ContextReferenceResult:
    """
    预处理消息中的@引用

    Args:
        message: 用户消息
        cwd: 当前工作目录
        context_length: 上下文长度（用于计算token限制）
        url_fetcher: URL获取函数（可选）

    Returns:
        ContextReferenceResult
    """
    refs = parse_context_references(message)
    if not refs:
        return ContextReferenceResult(
            message=message,
            original_message=message,
        )

    cwd_path = Path(cwd).expanduser().resolve()
    warnings: List[str] = []
    blocks: List[str] = []
    injected_tokens = 0

    # 先检查是否有敏感路径警告
    has_sensitive_warning = False
    for ref in refs:
        warning, block = _expand_reference(ref, cwd_path, url_fetcher)
        if warning and "sensitive" in warning.lower():
            has_sensitive_warning = True
        if warning:
            warnings.append(warning)
        if block:
            blocks.append(block)
            injected_tokens += _estimate_tokens(block)

    # Token限制
    hard_limit = max(1, int(context_length * 0.50))
    soft_limit = max(1, int(context_length * 0.25))

    # 敏感路径访问被阻止
    if has_sensitive_warning:
        warnings.append("@ context injection refused: sensitive path access denied.")
        return ContextReferenceResult(
            message=message,
            original_message=message,
            references=refs,
            warnings=warnings,
            injected_tokens=injected_tokens,
            expanded=False,
            blocked=True,
        )

    if injected_tokens > hard_limit:
        warnings.append(
            f"@ context injection refused: {injected_tokens} tokens exceeds the 50% hard limit ({hard_limit})."
        )
        return ContextReferenceResult(
            message=message,
            original_message=message,
            references=refs,
            warnings=warnings,
            injected_tokens=injected_tokens,
            expanded=False,
            blocked=True,
        )

    if injected_tokens > soft_limit:
        warnings.append(
            f"@ context injection warning: {injected_tokens} tokens exceeds the 25% soft limit ({soft_limit})."
        )

    # 构建最终消息
    stripped = _remove_reference_tokens(message, refs)
    final = stripped

    if warnings:
        final = f"{final}\n\n--- Context Warnings ---\n" + "\n".join(f"- {w}" for w in warnings)
    if blocks:
        final = f"{final}\n\n--- Attached Context ---\n\n" + "\n\n".join(blocks)

    return ContextReferenceResult(
        message=final.strip(),
        original_message=message,
        references=refs,
        warnings=warnings,
        injected_tokens=injected_tokens,
        expanded=True,
        blocked=False,
    )


# ============================================================================
# Hermès兼容工具函数
# ============================================================================

# Trailing punctuation to strip from reference values
TRAILING_PUNCTUATION = ",.;!?"


def _strip_trailing_punctuation(value: str) -> str:
    """去除引用值末尾的标点符号（Hermès兼容）"""
    stripped = value.rstrip(TRAILING_PUNCTUATION)
    while stripped.endswith((")", "]", "}")):
        closer = stripped[-1]
        opener = {")": "(", "]": "[", "}": "{"}[closer]
        if stripped.count(closer) > stripped.count(opener):
            stripped = stripped[:-1]
            continue
        break
    return stripped


def _strip_reference_wrappers(value: str) -> str:
    """去除引用值的反引号包裹（Hermès兼容）"""
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "`\"'":
        return value[1:-1]
    return value


def _is_binary_file(path: Path) -> bool:
    """检查文件是否为二进制（Hermès兼容）"""
    import mimetypes
    mime, _ = mimetypes.guess_type(path.name)
    if mime and not mime.startswith("text/") and not any(
        path.name.endswith(ext) for ext in (".py", ".md", ".txt", ".json", ".yaml", ".yml", ".toml", ".js", ".ts")
    ):
        return True
    chunk = path.read_bytes()[:4096]
    return b"\x00" in chunk


def _rg_files(path: Path, cwd: Path, limit: int) -> list | None:
    """使用ripgrep列出path中的文件（Hermès兼容）"""
    import subprocess
    try:
        result = subprocess.run(
            ["rg", "--files", ".", "--color", "never", "-0", "-m", str(limit), "--", "."],
            cwd=path,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            files = [Path(p) for p in result.stdout.strip("\0").split("\0") if p]
            return [f for f in files if f.is_file()]
    except Exception:
        pass
    return None


def _iter_visible_entries(path: Path, cwd: Path, limit: int) -> list:
    """遍历可见的目录条目（Hermès兼容）"""
    rg_entries = _rg_files(path, cwd, limit=limit)
    if rg_entries is not None:
        output = []
        seen_dirs = set()
        for rel in rg_entries:
            full = cwd / rel
            for parent in full.parents:
                if parent == cwd or parent in seen_dirs or path not in {parent, *parent.parents}:
                    continue
                seen_dirs.add(parent)
                output.append(parent)
            output.append(full)
        return sorted({p for p in output if p.exists()}, key=lambda p: (not p.is_dir(), str(p)))

    output = []
    for root, dirs, files in os.walk(path):
        dirs[:] = sorted(d for d in dirs if not d.startswith(".") and d != "__pycache__")
        files = sorted(f for f in files if not f.startswith("."))
        root_path = Path(root)
        for d in dirs:
            output.append(root_path / d)
            if len(output) >= limit:
                return output
        for f in files:
            output.append(root_path / f)
            if len(output) >= limit:
                return output
    return output


def _file_metadata(path: Path) -> str:
    """获取文件的元数据字符串（大小）（Hermès兼容）"""
    try:
        size = path.stat().st_size
        if size < 1024:
            return f"{size}B"
        elif size < 1024 * 1024:
            return f"{size / 1024:.1f}KB"
        else:
            return f"{size / (1024 * 1024):.1f}MB"
    except Exception:
        return "?"


def _code_fence_language(path: Path) -> str:
    """根据文件扩展名返回code fence语言标识符（Hermès兼容）"""
    ext_map = {
        ".py": "python",
        ".js": "javascript",
        ".ts": "typescript",
        ".jsx": "jsx",
        ".tsx": "tsx",
        ".md": "markdown",
        ".json": "json",
        ".yaml": "yaml",
        ".yml": "yaml",
        ".sh": "bash",
        ".bash": "bash",
        ".zsh": "bash",
        ".sql": "sql",
        ".html": "html",
        ".css": "css",
        ".go": "go",
        ".rs": "rust",
        ".java": "java",
        ".c": "c",
        ".cpp": "cpp",
        ".h": "c",
        ".hpp": "cpp",
    }
    return ext_map.get(path.suffix.lower(), "")


def _build_folder_listing(path: Path, cwd: Path, limit: int = 200) -> str:
    """构建文件夹列表字符串（Hermès兼容）"""
    lines = [f"{path.relative_to(cwd)}/"]
    entries = _iter_visible_entries(path, cwd, limit=limit)
    for entry in entries:
        rel = entry.relative_to(cwd)
        indent = "  " * max(len(rel.parts) - len(path.relative_to(cwd).parts) - 1, 0)
        if entry.is_dir():
            lines.append(f"{indent}- {entry.name}/")
        else:
            meta = _file_metadata(entry)
            lines.append(f"{indent}- {entry.name} ({meta})")
    if len(entries) >= limit:
        lines.append("- ...")
    return "\n".join(lines)


# ============================================================================
# 测试
# ============================================================================

if __name__ == "__main__":
    import tempfile
    import os

    print("=" * 60)
    print("Context References 测试")
    print("=" * 60)

    # 测试1: parse_context_references
    print("\n[测试1] parse_context_references")
    message = "Show me @diff and @staged changes. Also @file:README.md and @folder:src"
    refs = parse_context_references(message)
    print(f"  消息: {message}")
    print(f"  引用数: {len(refs)}")
    for ref in refs:
        print(f"    - kind={ref.kind}, target={ref.target}, raw={ref.raw}")
    assert len(refs) == 4
    print("  ✅ 通过")

    # 测试2: parse_context_references with line numbers
    print("\n[测试2] 行号解析")
    message2 = "@file:src/main.py:10-20"
    refs2 = parse_context_references(message2)
    assert len(refs2) == 1
    assert refs2[0].kind == "file"
    assert refs2[0].target == "src/main.py"
    assert refs2[0].line_start == 10
    assert refs2[0].line_end == 20
    print(f"  引用: kind={refs2[0].kind}, target={refs2[0].target}, lines={refs2[0].line_start}-{refs2[0].line_end}")
    print("  ✅ 通过")

    # 测试3: 敏感路径检查
    print("\n[测试3] 敏感路径检查")
    sensitive_paths = [
        "/home/user/.ssh/id_rsa",
        "~/.aws/credentials",
        "/home/user/.gnupg/secring.gpg",
    ]
    for path in sensitive_paths:
        p = Path(path)
        assert _is_sensitive_path(p), f"Should be sensitive: {path}"
    print(f"  敏感路径检测: {len(sensitive_paths)} 个")
    print("  ✅ 通过")

    # 测试4: 安全文件读取
    print("\n[测试4] 安全文件读取")
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write("# Test file\nprint('hello')\n")
        temp_file = f.name
    try:
        content = _read_file_safe(Path(temp_file))
        assert content is not None
        assert "Test file" in content
        print(f"  读取内容: {len(content)} chars")
        print("  ✅ 通过")
    finally:
        os.unlink(temp_file)

    # 测试5: preprocess_context_references with file
    print("\n[测试5] preprocess_context_references")
    with tempfile.TemporaryDirectory() as tmpdir:
        # 创建测试文件
        test_file = os.path.join(tmpdir, "test.txt")
        with open(test_file, 'w') as f:
            f.write("Line 1\nLine 2\nLine 3\nLine 4\nLine 5\n")

        message = f"Read @file:{test_file}"
        result = preprocess_context_references(message, cwd=tmpdir)

        assert result.expanded == True
        assert len(result.references) == 1
        assert "Line 1" in result.message
        print(f"  expanded: {result.expanded}")
        print(f"  references: {len(result.references)}")
        print(f"  warnings: {result.warnings}")
        print("  ✅ 通过")

    # 测试6: 敏感路径拒绝
    print("\n[测试6] 敏感路径拒绝")
    message_ssh = "@file:~/.ssh/id_rsa"
    result_ssh = preprocess_context_references(message_ssh, cwd="/home/user")
    assert result_ssh.blocked == True
    assert len(result_ssh.warnings) > 0
    print(f"  blocked: {result_ssh.blocked}")
    print(f"  warning: {result_ssh.warnings[0]}")
    print("  ✅ 通过")

    # 测试7: _remove_reference_tokens
    print("\n[测试7] _remove_reference_tokens")
    message = "Hello @diff and @file:README.md world"
    refs = parse_context_references(message)
    stripped = _remove_reference_tokens(message, refs)
    print(f"  原始: {message}")
    print(f"  移除后: {stripped}")
    assert "@diff" not in stripped
    assert "@file" not in stripped
    print("  ✅ 通过")

    # 测试8: 空消息
    print("\n[测试8] 空消息")
    result_empty = preprocess_context_references("", cwd="/tmp")
    assert len(result_empty.references) == 0
    assert result_empty.message == ""
    print("  ✅ 通过")

    print("\n" + "=" * 60)
    print("所有测试通过!")
    print("=" * 60)