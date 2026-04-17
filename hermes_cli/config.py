#!/usr/bin/env python3
"""
MimirAether 配置系统

简单的配置管理，支持：
- 环境变量
- YAML配置文件
- 默认值

不复制Hermes复杂架构，直接实现我们需要的功能。
"""

import os
import yaml
from pathlib import Path
from typing import Any, Dict, Optional

# =============================================================================
# 路径
# =============================================================================

def get_config_home() -> Path:
    """获取配置目录"""
    return Path.home() / ".openclaw"

def get_config_path() -> Path:
    """获取配置文件路径"""
    return get_config_home() / "config.yaml"

# =============================================================================
# 加载配置
# =============================================================================

_config_cache: Optional[Dict[str, Any]] = None

def load_config() -> Dict[str, Any]:
    """
    加载配置（带缓存）
    
    配置优先级：
    1. 环境变量
    2. YAML配置文件
    3. 默认值
    """
    global _config_cache
    
    if _config_cache is not None:
        return _config_cache
    
    config = _load_yaml_config()
    _config_cache = config
    return config

def _load_yaml_config() -> Dict[str, Any]:
    """从YAML加载配置"""
    config_path = get_config_path()
    
    if not config_path.exists():
        return _get_default_config()
    
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            yaml_config = yaml.safe_load(f)
            if yaml_config is None:
                return _get_default_config()
            
            # 合并默认配置
            default = _get_default_config()
            return _merge_config(default, yaml_config)
    except Exception as e:
        print(f"Warning: Failed to load config: {e}")
        return _get_default_config()

def _get_default_config() -> Dict[str, Any]:
    """获取默认配置"""
    return {
        "model": {
            "default": os.environ.get("MIMIR_MODEL", "deepseek/deepseek-chat"),
            "provider": os.environ.get("MIMIR_PROVIDER", "deepseek"),
        },
        "api": {
            "base_url": os.environ.get("DEEPSEEK_API_BASE", "https://api.deepseek.com"),
            "timeout": 120,
        },
        "gateway": {
            "port": int(os.environ.get("MIMIR_PORT", "18999")),
            "adapters": os.environ.get("MIMIR_ADAPTERS", "telegram,feishu,discord").split(","),
        },
        "tools": {
            "enabled": True,
            "max_concurrent": 5,
        },
        "logging": {
            "level": os.environ.get("MIMIR_LOG_LEVEL", "INFO"),
        },
    }

def _merge_config(default: Dict, override: Dict) -> Dict:
    """深度合并配置"""
    result = default.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _merge_config(result[key], value)
        else:
            result[key] = value
    return result

# =============================================================================
# 读取原始配置
# =============================================================================

def read_raw_config() -> Dict[str, Any]:
    """读取YAML配置（不合并默认）"""
    config_path = get_config_path()
    
    if not config_path.exists():
        return {}
    
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f) or {}
    except Exception:
        return {}

# =============================================================================
# 工具函数
# =============================================================================

def get_model() -> str:
    """获取当前模型"""
    config = load_config()
    return config.get("model", {}).get("default", "deepseek/deepseek-chat")

def get_provider() -> str:
    """获取当前provider"""
    config = load_config()
    return config.get("model", {}).get("provider", "deepseek")

def get_gateway_port() -> int:
    """获取Gateway端口"""
    config = load_config()
    return config.get("gateway", {}).get("port", 18999)

def is_tool_enabled() -> bool:
    """工具是否启用"""
    config = load_config()
    return config.get("tools", {}).get("enabled", True)

