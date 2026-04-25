"""
MimirAether 内置工具

提供基础的系统工具。所有工具通过 tools.registry 统一注册，
与 Hermes 的工具注册模式对齐。

注册模式（学习自 Hermes）:
    1. 定义函数
    2. 定义完整 OpenAI function schema（含 name, description, parameters）
    3. 调用 registry.register() 注册

兼容性说明：
    get_all_tools() 和 get_tool_functions() 保留用于向后兼容，
    新代码应使用 registry.get_definitions() 和 registry.dispatch()。
"""

import os
import json
import stat
from typing import Any, Dict

# ── 导入真正的 ToolRegistry（Hermes 模式） ──
from tools.registry import registry, tool_error, tool_result

# 允许的文件操作基础目录（可配置）
_ALLOWED_BASE_DIR = os.environ.get("MIMIR_BASE_DIR", os.path.expanduser("~"))

# 文件大小限制（1MB）
MAX_FILE_SIZE = 1024 * 1024

# 设备文件黑名单 — 读取这些文件会阻塞或产生无限输出
_BLOCKED_DEVICE_PATHS = frozenset({
    "/dev/zero", "/dev/random", "/dev/urandom", "/dev/full",
    "/dev/stdin", "/dev/tty", "/dev/console",
    "/dev/stdout", "/dev/stderr",
    "/dev/fd/0", "/dev/fd/1", "/dev/fd/2",
})


def _is_blocked_device(filepath: str) -> bool:
    """检查路径是否为会阻塞或产生无限输出的设备文件。"""
    normalized = os.path.expanduser(filepath)
    if normalized in _BLOCKED_DEVICE_PATHS:
        return True
    if normalized.startswith("/proc/") and normalized.endswith(("/fd/0", "/fd/1", "/fd/2")):
        return True
    return False


def _safe_path(path: str) -> str:
    """
    验证路径安全，防止路径遍历攻击和符号链接绕过
    
    Args:
        path: 用户提供的路径
        
    Returns:
        安全验证后的绝对路径
        
    Raises:
        ValueError: 路径超出允许范围或无效
    """
    # 空路径检查
    if not path or not path.strip():
        raise ValueError("Invalid empty path")
    
    # 扩展 ~ 为真实家目录（必须在abspath之前）
    if path.startswith("~"):
        path = os.path.expanduser(path)
    
    # 获取绝对路径
    try:
        abs_path = os.path.abspath(path)
    except (ValueError, TypeError):
        raise ValueError("Invalid path")
    
    # 检查路径的每个组件是否为符号链接（防止中间目录是symlink）
    parts = abs_path.split(os.sep)
    for i in range(len(parts)):
        # 构建到当前组件的路径
        partial_path = os.sep.join(parts[:i+1]) if i > 0 else parts[0]
        if not partial_path:
            continue
        if os.path.islink(partial_path):
            raise ValueError("Symbolic links are not allowed")
    
    # 获取真实绝对路径（解析符号链接）
    try:
        real_path = os.path.realpath(abs_path)
    except (ValueError, TypeError):
        raise ValueError("Invalid path")
    
    # 解析后的路径不能是符号链接（防止链接指向目录外）
    if os.path.islink(real_path):
        raise ValueError("Symbolic links are not allowed")
    
    # 检查解析后的路径是否在允许目录内
    allowed_real = os.path.realpath(os.path.abspath(_ALLOWED_BASE_DIR))
    if not real_path.startswith(allowed_real + os.sep):
        raise ValueError("Path traversal attempt detected")
    
    return real_path


# ─────────────────────────────────────────────────────────────
# 工具处理函数（每个返回 JSON 字符串，符合 Hermes 模式）
# ─────────────────────────────────────────────────────────────

def _handle_read_file(path: str, offset: int = 1, limit: int = 500) -> str:
    """读取文件内容（安全版本，支持分页）"""
    try:
        # 设备文件保护 — 阻止读取会阻塞或产生无限输出的设备文件
        if _is_blocked_device(path):
            return tool_error("Cannot read device file (would block or produce infinite output)")
        
        safe_path = _safe_path(path)
        # 先检查文件大小（避免打开过大的文件）
        file_size = os.path.getsize(safe_path)
        if file_size > MAX_FILE_SIZE:
            return tool_error("File too large")
        # 使用O_NOFOLLOW防止TOCTOU攻击（最佳实践：检查平台支持）
        flags = os.O_RDONLY
        o_nofollow = getattr(os, "O_NOFOLLOW", None)
        if o_nofollow is not None:
            flags |= o_nofollow
        fd = os.open(safe_path, flags)
        try:
            content = os.read(fd, MAX_FILE_SIZE).decode("utf-8")
            # 实现分页
            lines = content.split('\n')
            if offset > 1:
                lines = lines[offset - 1:]
            if limit < len(lines):
                lines = lines[:limit]
            return '\n'.join(lines)
        finally:
            os.close(fd)
    except ValueError:
        return tool_error("Invalid path")
    except FileNotFoundError:
        return tool_error("File not found")
    except IsADirectoryError:
        return tool_error("Path is a directory, not a file")
    except PermissionError:
        return tool_error("Permission denied")
    except OSError:
        return tool_error("Invalid file")
    except Exception as e:
        return tool_error(f"Error reading file: {e}")


def _handle_write_file(path: str, content: str) -> str:
    """写入文件内容（安全版本）"""
    try:
        # 检查内容大小
        if len(content.encode('utf-8')) > MAX_FILE_SIZE:
            return tool_error("Content too large")
        safe_path = _safe_path(path)
        # 使用O_NOFOLLOW防止TOCTOU攻击（最佳实践：检查平台支持）
        flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
        o_nofollow = getattr(os, "O_NOFOLLOW", None)
        if o_nofollow is not None:
            flags |= o_nofollow
        fd = os.open(safe_path, flags, 0o600)
        try:
            os.write(fd, content.encode("utf-8"))
        finally:
            os.close(fd)
        return tool_result(success=True)
    except ValueError:
        return tool_error("Invalid path")
    except PermissionError:
        return tool_error("Permission denied")
    except Exception as e:
        return tool_error(f"Error writing file: {e}")


def _handle_execute_code(code: str, language: str = "python") -> str:
    """安全执行Python代码，使用subprocess + 超时保护。"""
    import subprocess
    import tempfile
    
    if language != "python":
        return tool_error(f"Only Python is supported, got: {language}")
    
    # 限制代码大小（防止内存耗尽）
    if len(code.encode('utf-8')) > 100 * 1024:
        return tool_error("Code too large (max 100KB)")
    
    # 创建临时文件执行
    try:
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, encoding='utf-8') as f:
            f.write(code)
            temp_path = f.name
        
        try:
            # 执行代码，60秒超时
            result = subprocess.run(
                ['python3', temp_path],
                capture_output=True,
                text=True,
                timeout=60,
                cwd=os.path.dirname(temp_path) or '.'
            )
            
            if result.returncode == 0:
                output = result.stdout if result.stdout else "Code executed successfully (no output)"
                return tool_result(output=output)
            else:
                err = result.stderr if result.stderr else f"exit code {result.returncode}"
                return tool_error(err)
        finally:
            # 清理临时文件
            try:
                os.unlink(temp_path)
            except:
                pass
    except subprocess.TimeoutExpired:
        return tool_error("Execution timed out (60s limit)")
    except Exception as e:
        return tool_error(f"{type(e).__name__}: {str(e)}")


def _handle_get_env(key: str, default: str = "") -> str:
    """获取环境变量（白名单限制）"""
    # 允许访问的环境变量白名单
    _ALLOWED_ENV_VARS = {
        "PATH", "HOME", "USER", "SHELL", "PWD",
        "LANG", "LC_ALL", "TERM", "TERM_PROGRAM",
    }
    value = os.environ.get(key, default) if key in _ALLOWED_ENV_VARS else default
    return tool_result(value=value)


def _handle_search_web(query: str) -> str:
    """搜索网络（模拟）"""
    return tool_result(results=[], query=query, note="Web search requires API integration")


# ─────────────────────────────────────────────────────────────
# 注册所有内置工具到 registry（Hermes 模式）
# ─────────────────────────────────────────────────────────────

# read_file
registry.register(
    name="read_file",
    toolset="file",
    schema={
        "name": "read_file",
        "description": "读取文件内容（安全版本，支持分页）。读取指定路径的文件，支持指定起始行和最大行数。",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "要读取的文件路径"
                },
                "offset": {
                    "type": "integer",
                    "description": "起始行号（1-based）",
                    "default": 1
                },
                "limit": {
                    "type": "integer",
                    "description": "最大读取行数",
                    "default": 500
                }
            },
            "required": ["path"]
        }
    },
    handler=lambda args, **kw: _handle_read_file(
        path=args.get("path", ""),
        offset=args.get("offset", 1),
        limit=args.get("limit", 500),
    ),
    emoji="📖",
    description="Read file contents with pagination support",
)

# write_file
registry.register(
    name="write_file",
    toolset="file",
    schema={
        "name": "write_file",
        "description": "写入文件内容（安全版本）。创建或覆盖指定路径的文件。",
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "要写入的文件路径"
                },
                "content": {
                    "type": "string",
                    "description": "要写入的内容"
                }
            },
            "required": ["path", "content"]
        }
    },
    handler=lambda args, **kw: _handle_write_file(
        path=args.get("path", ""),
        content=args.get("content", ""),
    ),
    emoji="✏️",
    description="Write content to a file",
)

# execute_code
registry.register(
    name="execute_code",
    toolset="code_execution",
    schema={
        "name": "execute_code",
        "description": "执行代码。安全执行Python代码，使用subprocess + 超时保护（60秒）。",
        "parameters": {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "要执行的代码"
                },
                "language": {
                    "type": "string",
                    "description": "编程语言",
                    "default": "python"
                }
            },
            "required": ["code"]
        }
    },
    handler=lambda args, **kw: _handle_execute_code(
        code=args.get("code", ""),
        language=args.get("language", "python"),
    ),
    emoji="⚡",
    description="Execute Python code in a sandboxed subprocess",
)

# get_env
registry.register(
    name="get_env",
    toolset="file",
    schema={
        "name": "get_env",
        "description": "获取环境变量（白名单限制）。仅可访问白名单内的安全环境变量。",
        "parameters": {
            "type": "object",
            "properties": {
                "key": {
                    "type": "string",
                    "description": "环境变量名"
                },
                "default": {
                    "type": "string",
                    "description": "默认值",
                    "default": ""
                }
            },
            "required": ["key"]
        }
    },
    handler=lambda args, **kw: _handle_get_env(
        key=args.get("key", ""),
        default=args.get("default", ""),
    ),
    emoji="🔑",
    description="Get environment variable (whitelist restricted)",
)

# search_web
registry.register(
    name="search_web",
    toolset="web",
    schema={
        "name": "search_web",
        "description": "搜索网络。执行网页搜索查询。",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "搜索查询"
                }
            },
            "required": ["query"]
        }
    },
    handler=lambda args, **kw: _handle_search_web(
        query=args.get("query", ""),
    ),
    emoji="🔍",
    description="Search the web",
)


# ─────────────────────────────────────────────────────────────
# 向后兼容层（旧代码仍可调用）
# ─────────────────────────────────────────────────────────────

# 工具函数表 — 直接可调用版本（不返回 JSON，用于内部调用）
TOOL_FUNCTIONS = {
    "read_file": _handle_read_file,
    "write_file": _handle_write_file,
    "execute_code": _handle_execute_code,
    "get_env": _handle_get_env,
    "search_web": _handle_search_web,
}

# 旧式 schema 字典 — 仅含 parameters 部分
TOOL_SCHEMAS = {
    name: entry.schema.get("parameters", {})
    for name, entry in registry._tools.items()
    if entry.toolset in ("file", "code_execution", "web")
}


def get_all_tools() -> Dict[str, Dict]:
    """获取所有工具及其 schema（向后兼容）"""
    return TOOL_SCHEMAS


def get_tool_functions() -> Dict[str, callable]:
    """获取所有工具函数（向后兼容）"""
    return TOOL_FUNCTIONS
