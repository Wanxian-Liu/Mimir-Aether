"""
Tool Argument Repair — P0-1: 参数修复地狱 120 行 → 独立模块

从 core_loop._execute_single_tool 提取的参数修复逻辑：
- execute_code sindri 修复 (raw string → {code: ...})
- write_file sindri 修复 (6 步回退解析)
- 通用修复 (JSON 解析 + 字段提取)

所有修复函数签名: RepairFn(raw_args: Any) → Optional[Dict[str, Any]]
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


# ============================================================================
# write_file 参数修复 (P0-1b: 从 core_loop 迁移)
# ============================================================================

def repair_write_file_args(raw_args: str) -> Optional[Dict[str, Any]]:
    """Best-effort parse of write_file arguments from a raw string.
    
    Used when ``json.loads(raw_args)`` fails. Order: strict JSON (again after
    ``\"`` unescape), regex path/content extraction, ``path|content`` split,
    legacy truncated-JSON suffix heuristic.
    """
    if not isinstance(raw_args, str) or not raw_args.strip():
        return None

    # 1. Retry strict JSON
    try:
        d = json.loads(raw_args)
        return d if isinstance(d, dict) else None
    except json.JSONDecodeError:
        pass

    # 2. Unescape backslashes then retry
    try:
        d = json.loads(raw_args.replace('\\"', '"'))
        return d if isinstance(d, dict) else None
    except json.JSONDecodeError:
        pass

    # 3. Regex extract path + content
    path_match = re.search(r'"path"\s*:\s*"([^"]*)"', raw_args)
    content_match = re.search(r'"content"\s*:\s*"(.*?)"(?:\s*[,}])', raw_args, re.DOTALL)
    if path_match:
        path_val = path_match.group(1)
        content_val = content_match.group(1) if content_match else ""
        content_val = content_val.replace('\\"', '"').replace('\\n', '\n').replace('\\t', '\t')
        return {"path": path_val, "content": content_val}

    # 4. path|content split
    if "|" in raw_args:
        parts = raw_args.split("|", 1)
        return {"path": parts[0], "content": parts[1] if len(parts) > 1 else ""}

    # 5. Truncated JSON suffix fix
    try:
        fixed = raw_args.rstrip()
        if not fixed.endswith("}"):
            fixed = fixed + '"}}'
        d = json.loads(fixed)
        return d if isinstance(d, dict) else None
    except json.JSONDecodeError:
        pass

    return None


# ============================================================================
# execute_code 参数修复
# ============================================================================

def repair_execute_code_args(raw_args: Any) -> Optional[Dict[str, Any]]:
    """Fix execute_code arguments: raw string → {code: ...}"""
    if isinstance(raw_args, str):
        logger.info("execute_code: sindri fix - wrapping raw code string as {code: ...}")
        return {"code": raw_args}
    return None


# ============================================================================
# 深度修复: execute_code 字段提取
# ============================================================================

def deep_repair_execute_code_args(arguments: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """If arguments is a dict but missing 'code', try extracting from other fields."""
    if "code" in arguments:
        return None  # No repair needed
    
    if len(arguments) == 1 and "type" in arguments:
        # OpenAI 嵌套格式，跳过
        return None
    
    logger.warning("execute_code: no 'code' field in arguments, attempting repair")
    for key, val in arguments.items():
        if key != "type" and isinstance(val, str):
            logger.info("execute_code: using field '%s' as code", key)
            return {"code": val}
    
    return None


# ============================================================================
# 统一修复入口 (P0-1c)
# ============================================================================

def repair_tool_arguments(
    func_name: str,
    raw_args: Any,
) -> Dict[str, Any]:
    """统一工具参数修复入口。
    
    替换 core_loop._execute_single_tool 中 ~55 行的 ad-hoc 修复逻辑。
    
    Args:
        func_name: 工具名称
        raw_args: 原始参数（dict 或 str）
        
    Returns:
        修复后的参数 dict。如果无法修复，返回 {"raw": str(raw_args)}
    """
    # 1. 类型标准化
    if isinstance(raw_args, dict):
        arguments = raw_args
    elif isinstance(raw_args, str):
        try:
            arguments = json.loads(raw_args)
        except json.JSONDecodeError as e:
            logger.warning(
                "SINDRI_DEBUG: JSONDecodeError for %s, raw_args len=%d, chars=%s",
                func_name, len(str(raw_args)), repr(str(raw_args)[:200])
            )
            # 2. 工具特定修复
            if func_name == "execute_code":
                repaired = repair_execute_code_args(raw_args)
                if repaired is not None:
                    return repaired
            elif func_name == "write_file":
                repaired = repair_write_file_args(raw_args)
                if repaired is not None:
                    logger.info(
                        "write_file: repaired arguments path_len=%d content_len=%d",
                        len(str(repaired.get("path", ""))),
                        len(str(repaired.get("content", ""))),
                    )
                    return repaired
            
            # 3. 兜底: 将 raw_args 作为纯字符串处理
            logger.info("Unknown tool %s: treating raw_args as string", func_name)
            return {"raw": raw_args}
    else:
        arguments = {}

    # 4. 深度修复: execute_code 字段提取
    if func_name == "execute_code" and isinstance(arguments, dict):
        deep_fix = deep_repair_execute_code_args(arguments)
        if deep_fix is not None:
            return deep_fix

    return arguments
