"""MimirAether专用常量 - 兼容层"""

import os
from pathlib import Path

# 从mimir_constants导入核心函数
from mimir_constants import get_mimir_home, MIMIR_HOME

# 向后兼容别名
def get_mimiraether_home() -> Path:
    return get_mimir_home()

def get_hermes_home() -> Path:
    """Alias for backward compatibility."""
    return get_mimir_home()

HERMES_HOME = MIMIR_HOME
MIMIRAETHER_HOME = MIMIR_HOME

def get_config_path() -> Path:
    """Return the path to config.yaml under MIMIRAETHER_HOME."""
    return get_mimir_home() / "config.yaml"

def managed_nous_tools_enabled() -> bool:
    """Return True when Nous-managed tools feature flag is enabled."""
    from utils import env_var_enabled
    return env_var_enabled("HERMES_ENABLE_NOUS_MANAGED_TOOLS")
