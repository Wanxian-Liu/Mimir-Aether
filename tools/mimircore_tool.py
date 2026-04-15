"""
MimirCoreTool - 调用Mimir-Core胶囊生成能力

Mimir-Core是MimirAether的知识工厂，负责生成高质量胶囊。
这个工具让MimirAether能够调用Mimir-Core的胶囊生成能力。

使用方式：
    MimirAether发现有价值知识 → 调用produce_capsule → 生成胶囊 → GDI评分 → 发布

Mimir-Core路径：
    ~/.openclaw/projects/Mimir-Core/
"""

import sys
import os
from pathlib import Path
from typing import Dict, Any, Optional

# Mimir-Core路径
MIMIR_CORE_PATH = os.path.expanduser("~/.openclaw/projects/Mimir-Core")


def _ensure_mimircore_importable():
    """确保Mimir-Core模块可导入"""
    if MIMIR_CORE_PATH not in sys.path:
        sys.path.insert(0, MIMIR_CORE_PATH)


def produce_capsule(input_text: str, capsule_type: str = "auto", auto_publish: bool = True) -> str:
    """
    调用Mimir-Core生成胶囊
    
    Mimir-Core是MimirAether的知识工厂，通过这个工具调用其胶囊生成能力。
    
    Args:
        input_text: 要生成胶囊的知识内容
        capsule_type: 胶囊类型 ("auto", "innovate", "optimize", "repair")
        auto_publish: 是否自动发布（仅当GDI≥70时）
    
    Returns:
        生成结果的描述字符串
    """
    _ensure_mimircore_importable()
    
    try:
        from capsule_generator import CapsuleGenerator, CapsuleType
        
        # 类型映射
        type_map = {
            "auto": None,
            "innovate": CapsuleType.INNOVATE,
            "optimize": CapsuleType.OPTIMIZE,
            "repair": CapsuleType.REPAIR,
        }
        cap_type = type_map.get(capsule_type.lower(), None)
        
        # 生成胶囊
        generator = CapsuleGenerator()
        result = generator.generate_and_evaluate(
            input_text=input_text,
            auto_publish=auto_publish,
            metadata={"source": "MimirAether", "capsule_type": capsule_type}
        )
        
        capsule = result.get("capsule")
        gdi_score = result.get("gdi_score")
        should_publish = result.get("should_publish", False)
        reason = result.get("reason", "")
        
        # 构建返回信息
        gdi_value = gdi_score.total if gdi_score else 0
        capsule_id = capsule.id if capsule else "unknown"
        
        output = []
        output.append(f"[MimirCore胶囊生成]")
        output.append(f"胶囊ID: {capsule_id}")
        output.append(f"GDI评分: {gdi_value}")
        output.append(f"建议: {reason}")
        
        if should_publish and auto_publish:
            output.append("状态: ✅ 已发布到public/")
        elif should_publish:
            output.append("状态: 待发布（GDI≥70，可调用publish_capsule发布）")
        else:
            output.append(f"状态: ❌ 未达标（GDI<70，需优化）")
        
        return "\n".join(output)
        
    except ImportError as e:
        return f"[MimirCore错误] 无法导入Mimir-Core模块: {e}"
    except Exception as e:
        return f"[MimirCore错误] {type(e).__name__}: {str(e)}"


def get_capsule_by_id(capsule_id: str) -> str:
    """
    根据ID获取胶囊详情
    
    Args:
        capsule_id: 胶囊ID
    
    Returns:
        胶囊详情描述
    """
    _ensure_mimircore_importable()
    
    try:
        import json
        from pathlib import Path
        
        public_dir = Path(MIMIR_CORE_PATH) / "public"
        
        # 搜索胶囊文件
        for capsule_file in public_dir.glob("*.md"):
            content = capsule_file.read_text()
            if capsule_id in capsule_file.stem or capsule_id in content[:200]:
                # 找到胶囊，返回基本信息
                lines = content.split("\n")
                return f"[胶囊详情]\n文件: {capsule_file.name}\n内容预览: {content[:500]}..."
        
        return f"[MimirCore] 未找到胶囊: {capsule_id}"
        
    except Exception as e:
        return f"[MimirCore错误] {type(e).__name__}: {str(e)}"


def list_capsules(tag_filter: str = None, limit: int = 20) -> str:
    """
    列出胶囊
    
    Args:
        tag_filter: 标签过滤（可选）
        limit: 返回数量限制
    
    Returns:
        胶囊列表描述
    """
    _ensure_mimircore_importable()
    
    try:
        from pathlib import Path
        
        public_dir = Path(MIMIR_CORE_PATH) / "public"
        capsules = sorted(public_dir.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True)
        
        if tag_filter:
            capsules = [c for c in capsules if tag_filter.lower() in c.stem.lower()]
        
        capsules = capsules[:limit]
        
        output = ["[MimirCore胶囊列表]"]
        output.append(f"总数: {len(capsules)} (显示前{len(capsules)}个)")
        output.append("")
        
        for capsule in capsules:
            output.append(f"- {capsule.stem}")
        
        return "\n".join(output)
        
    except Exception as e:
        return f"[MimirCore错误] {type(e).__name__}: {str(e)}"


def improve_capsule(capsule_id: str, improvement_hint: str) -> str:
    """
    改进胶囊
    
    Args:
        capsule_id: 胶囊ID
        improvement_hint: 改进提示
    
    Returns:
        改进结果描述
    """
    _ensure_mimircore_importable()
    
    try:
        # 先获取原胶囊内容
        capsule_detail = get_capsule_by_id(capsule_id)
        
        # 用改进提示重新生成
        improved_text = f"{capsule_detail}\n\n[改进要求]: {improvement_hint}"
        
        return produce_capsule(improved_text, capsule_type="optimize", auto_publish=True)
        
    except Exception as e:
        return f"[MimirCore错误] {type(e).__name__}: {str(e)}"


# 工具schema定义
TOOL_SCHEMAS = {
    "produce_capsule": {
        "description": "调用Mimir-Core生成胶囊。Mimir-Core是MimirAether的知识工厂，负责生成高质量胶囊。输入知识内容，输出评分≥70的胶囊。",
        "parameters": {
            "type": "object",
            "properties": {
                "input_text": {
                    "type": "string",
                    "description": "要生成胶囊的知识内容（可以是技术文档、经验总结、解决方案等）"
                },
                "capsule_type": {
                    "type": "string",
                    "description": "胶囊类型",
                    "enum": ["auto", "innovate", "optimize", "repair"],
                    "default": "auto"
                },
                "auto_publish": {
                    "type": "boolean",
                    "description": "是否自动发布（GDI≥70时）",
                    "default": True
                }
            },
            "required": ["input_text"]
        }
    },
    "get_capsule_by_id": {
        "description": "根据ID获取胶囊详情",
        "parameters": {
            "type": "object",
            "properties": {
                "capsule_id": {
                    "type": "string",
                    "description": "胶囊ID"
                }
            },
            "required": ["capsule_id"]
        }
    },
    "list_capsules": {
        "description": "列出所有胶囊",
        "parameters": {
            "type": "object",
            "properties": {
                "tag_filter": {
                    "type": "string",
                    "description": "标签过滤（可选）"
                },
                "limit": {
                    "type": "integer",
                    "description": "返回数量限制",
                    "default": 20
                }
            }
        }
    },
    "improve_capsule": {
        "description": "改进现有胶囊",
        "parameters": {
            "type": "object",
            "properties": {
                "capsule_id": {
                    "type": "string",
                    "description": "要改进的胶囊ID"
                },
                "improvement_hint": {
                    "type": "string",
                    "description": "改进提示"
                }
            },
            "required": ["capsule_id", "improvement_hint"]
        }
    }
}


def get_tool_functions() -> Dict[str, callable]:
    """获取所有工具函数"""
    return {
        "produce_capsule": produce_capsule,
        "get_capsule_by_id": get_capsule_by_id,
        "list_capsules": list_capsules,
        "improve_capsule": improve_capsule,
    }
