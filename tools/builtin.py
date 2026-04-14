"""
MimirAether 内置工具

提供基础的系统工具。
"""

import os
import json
from typing import Any, Dict

# 允许的文件操作基础目录（可配置）
_ALLOWED_BASE_DIR = os.environ.get("MIMIR_BASE_DIR", os.path.expanduser("~"))


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
    
    # 获取绝对路径
    try:
        abs_path = os.path.abspath(path)
    except (ValueError, TypeError):
        raise ValueError("Invalid path")
    
    # 检查路径本身是否为符号链接（直接攻击）
    if os.path.islink(abs_path):
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


def read_file(path: str) -> str:
    """
    读取文件内容（安全版本）
    
    Args:
        path: 文件路径
        
    Returns:
        文件内容字符串
    """
    try:
        safe_path = _safe_path(path)
        with open(safe_path, "r", encoding="utf-8") as f:
            return f.read()
    except ValueError as e:
        return f"Error: {e}"
    except FileNotFoundError:
        return "Error: File not found"
    except IsADirectoryError:
        return "Error: Path is a directory, not a file"
    except Exception as e:
        return "Error reading file"


def write_file(path: str, content: str) -> str:
    """
    写入文件内容（安全版本）
    
    Args:
        path: 文件路径
        content: 要写入的内容
        
    Returns:
        成功消息或错误信息
    """
    try:
        safe_path = _safe_path(path)
        with open(safe_path, "w", encoding="utf-8") as f:
            f.write(content)
        return "Successfully wrote file"
    except ValueError as e:
        return f"Error: {e}"
    except Exception as e:
        return "Error writing file"


def execute_code(code: str, language: str = "python") -> str:
    """
    执行代码
    
    注意：此为占位实现，实际执行需要沙盒环境。
    直接执行用户代码可能导致安全问题。
    
    Args:
        code: 要执行的代码
        language: 编程语言
        
    Returns:
        执行结果或错误信息
    """
    return "Error: execute_code is not yet implemented. Code execution requires a sandbox environment."


# 允许访问的环境变量白名单
_ALLOWED_ENV_VARS = {
    "PATH", "HOME", "USER", "SHELL", "PWD",
    "LANG", "LC_ALL", "TERM", "TERM_PROGRAM",
}

def get_env(key: str, default: str = "") -> str:
    """
    获取环境变量（白名单限制）
    
    Args:
        key: 环境变量名
        default: 默认值
        
    Returns:
        环境变量值或默认值（仅限白名单内的变量）
    """
    if key in _ALLOWED_ENV_VARS:
        return os.environ.get(key, default)
    return default


def search_web(query: str) -> str:
    """
    搜索网络（模拟）
    
    注意：实际搜索需要API
    
    Args:
        query: 搜索查询
        
    Returns:
        搜索结果或错误信息
    """
    return f"[Simulated] Would search web for: {query}"


# 工具 schema 定义
TOOL_SCHEMAS = {
    "read_file": {
        "parameters": {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "要读取的文件路径"
                }
            },
            "required": ["path"]
        }
    },
    "write_file": {
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
    "execute_code": {
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
    "get_env": {
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
    "search_web": {
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
    }
}


def get_all_tools() -> Dict[str, Dict]:
    """获取所有工具及其 schema"""
    return TOOL_SCHEMAS


def get_tool_functions() -> Dict[str, callable]:
    """获取所有工具函数"""
    return {
        "read_file": read_file,
        "write_file": write_file,
        "execute_code": execute_code,
        "get_env": get_env,
        "search_web": search_web
    }
