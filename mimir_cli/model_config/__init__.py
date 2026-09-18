"""
记忆殿堂v2.0 配置模块

用法:
    from config import load_config, get_config
    
    # 加载全部配置
    config = load_config()
    
    # 获取特定配置
    cache_size = get_config('cache', 'lru', 'memory_cache_size')
    
    # 环境变量覆盖示例:
    # export MEMORY_HALL_CACHE_LRU_MEMORY_CACHE_SIZE=200
"""

from .loader import (
    ConfigLoader,
    get_loader,
    load_config,
    get_config,
)

__all__ = [
    'ConfigLoader',
    'get_loader',
    'load_config',
    'get_config',
]

__version__ = '2.0.0'
