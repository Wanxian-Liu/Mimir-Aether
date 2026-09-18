"""
记忆殿堂v2.0 配置加载器
支持YAML配置 + 环境变量覆盖

环境变量格式: MEMORY_HALL_* 前缀
示例:
  MEMORY_HALL_STORAGE_BASE_DIR -> storage.base_dir
  MEMORY_HALL_CACHE_LRU_MEMORY_CACHE_SIZE -> cache.lru.memory_cache_size
  MEMORY_HALL_PERMISSIONS_FENCE_ENABLED -> permissions.fence.enabled
"""

import os
import yaml
from pathlib import Path
from typing import Any, Dict, Optional


class ConfigLoader:
    """配置加载器"""
    
    ENV_PREFIX = "MEMORY_HALL_"
    
    def __init__(self, config_path: Optional[str] = None):
        if config_path is None:
            config_path = Path(__file__).parent / "config.yaml"
        self.config_path = Path(config_path)
        self._config: Optional[Dict[str, Any]] = None
    
    def load(self) -> Dict[str, Any]:
        """加载配置（带缓存）"""
        if self._config is None:
            self._config = self._load_yaml()
            self._apply_env_overrides()
            self._resolve_paths()
        return self._config
    
    def _load_yaml(self) -> Dict[str, Any]:
        """从YAML文件加载配置"""
        if not self.config_path.exists():
            raise FileNotFoundError(f"配置文件不存在: {self.config_path}")
        
        with open(self.config_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f) or {}
    
    def _apply_env_overrides(self):
        """应用环境变量覆盖"""
        for key, value in os.environ.items():
            if not key.startswith(self.ENV_PREFIX):
                continue
            
            # 转换键名: STORAGE_BASE_DIR -> storage.base_dir
            dotted_key = key[len(self.ENV_PREFIX):].lower()
            # 特殊处理多层嵌套
            parts = self._parse_dotted_key(dotted_key)
            
            if parts:
                self._set_nested(self._config, parts, self._parse_value(value))
    
    def _parse_dotted_key(self, key: str) -> list:
        """解析点分隔的键名"""
        # 预定义路径映射（因为YAML键名与ENV键名可能不完全匹配）
        mapping = {
            'storage': ['storage'],
            'storage_base_dir': ['storage', 'base_dir'],
            'storage_memory_daily_dir': ['storage', 'memory', 'daily_dir'],
            'storage_memory_longterm_file': ['storage', 'memory', 'longterm_file'],
            'cache': ['cache'],
            'cache_lru_memory_cache_size': ['cache', 'lru', 'memory_cache_size'],
            'cache_lru_search_cache_size': ['cache', 'lru', 'search_cache_size'],
            'cache_lru_ttl': ['cache', 'lru', 'ttl'],
            'permissions': ['permissions'],
            'permissions_access_default_level': ['permissions', 'access', 'default_level'],
            'permissions_fence_enabled': ['permissions', 'fence', 'enabled'],
            'permissions_fence_violation_threshold': ['permissions', 'fence', 'violation_threshold'],
            'plugins': ['plugins'],
            'plugins_enabled': ['plugins', 'enabled'],
            'plugins_timeout': ['plugins', 'settings', 'timeout'],
            'logging_level': ['logging', 'level'],
        }
        
        # 尝试直接匹配
        if key in mapping:
            return mapping[key]
        
        # 尝试动态解析: storage_memory_daily_dir -> ['storage', 'memory', 'daily_dir']
        parts = []
        current = []
        for segment in key.split('_'):
            test = current + [segment]
            test_key = '_'.join(test)
            if '_'.join(test) in [k for k in mapping.keys() if k.startswith('_'.join(current))]:
                current.append(segment)
            else:
                if current:
                    parts.extend(current)
                    current = [segment]
                else:
                    current = [segment]
        if current:
            parts.extend(current)
        
        return parts
    
    def _set_nested(self, config: Dict, path: list, value: Any):
        """设置嵌套值"""
        current = config
        for key in path[:-1]:
            if key not in current:
                current[key] = {}
            current = current[key]
        current[path[-1]] = value
    
    def _parse_value(self, value: str) -> Any:
        """解析环境变量值"""
        # 布尔值
        if value.lower() in ('true', 'yes', '1'):
            return True
        if value.lower() in ('false', 'no', '0'):
            return False
        
        # 数字
        try:
            if '.' in value:
                return float(value)
            return int(value)
        except ValueError:
            pass
        
        # 列表（逗号分隔）
        if ',' in value:
            items = [item.strip() for item in value.split(',')]
            if all(item.isdigit() for item in items):
                return [int(item) for item in items]
            return items
        
        # 字符串
        return value
    
    def _resolve_paths(self):
        """解析路径中的~和环境变量"""
        self._resolve_paths_recursive(self._config)
    
    def _resolve_paths_recursive(self, obj: Any):
        """递归解析路径"""
        if isinstance(obj, dict):
            for key, value in obj.items():
                if isinstance(value, str) and value.startswith('~'):
                    obj[key] = os.path.expanduser(value)
                elif isinstance(value, (dict, list)):
                    self._resolve_paths_recursive(value)
        elif isinstance(obj, list):
            for i, item in enumerate(obj):
                if isinstance(item, str) and item.startswith('~'):
                    obj[i] = os.path.expanduser(item)
                elif isinstance(item, (dict, list)):
                    self._resolve_paths_recursive(item)
    
    def get(self, *keys, default=None) -> Any:
        """获取配置值"""
        config = self.load()
        current = config
        for key in keys:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return default
        return current
    
    def reload(self):
        """重新加载配置"""
        self._config = None
        return self.load()


# 单例模式
_instance: Optional[ConfigLoader] = None

def get_loader(config_path: Optional[str] = None) -> ConfigLoader:
    """获取配置加载器单例"""
    global _instance
    if _instance is None or config_path is not None:
        _instance = ConfigLoader(config_path)
    return _instance

def load_config() -> Dict[str, Any]:
    """加载配置（快捷函数）"""
    return get_loader().load()

def get_config(*keys, default=None) -> Any:
    """获取配置值（快捷函数）"""
    return get_loader().get(*keys, default=default)
