"""
MimirAether Tools

所有工具通过 tools.registry 统一注册（Hermes 模式）。
导入此包时会自动加载内置工具和 MimirCore 工具。
"""

# 导入 MimirCore 工具模块
from . import mimircore_tool


def check_file_requirements() -> bool:
    """Core file tools (read_file, write_file, patch, search_files) are always available."""
    return True
