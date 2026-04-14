"""
MimirAether 内置工具

提供基础的系统工具。
"""

import os
import json
from typing import Any, Dict


def read_file(path: str) -> str:
    """
    读取文件内容
    
    Args:
        path: 文件路径
        
    Returns:
        文件内容字符串
    """
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return f"Error: File not found: {path}"
    except Exception as e:
        return f"Error reading file: {e}"


def write_file(path: str, content: str) -> str:
    """
    写入文件内容
    
    Args:
        path: 文件路径
        content: 要写入的内容
        
    Returns:
        成功消息或错误信息
    """
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"Successfully wrote to {path}"
    except Exception as e:
        return f"Error writing file: {e}"


def execute_code(code: str, language: str = "python") -> str:
    """
    执行代码（模拟）
    
    注意：实际执行需要沙盒环境
    
    Args:
        code: 要执行的代码
        language: 编程语言
        
    Returns:
        执行结果或错误信息
    """
    return f"[Simulated] Would execute {language} code: {len(code)} characters"


def get_env(key: str, default: str = "") -> str:
    """
    获取环境变量
    
    Args:
        key: 环境变量名
        default: 默认值
        
    Returns:
        环境变量值或默认值
    """
    return os.environ.get(key, default)


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
