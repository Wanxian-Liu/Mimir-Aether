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