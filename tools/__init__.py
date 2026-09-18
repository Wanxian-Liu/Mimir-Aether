"""
MimirAether Tools

所有工具通过 tools.registry 统一注册（Hermes 模式）。
导入此包时会自动加载内置工具和 MimirCore 工具。
"""

# MimirCore/capsule 工具面已于 2026-09-18 整链归档（git mv -> scripts/legacy/capsule/
# mimircore_tool.py，A9 裁决=工具面整链归档）。此处不再 import：该模块已不在 tools/ 下。
# 允许 capsule 工具复活的前提是先走批4 防复发闸（ARCHIVED-IMPORT-FAIL）。


def check_file_requirements() -> bool:
    """Core file tools (read_file, write_file, patch, search_files) are always available."""
    return True
