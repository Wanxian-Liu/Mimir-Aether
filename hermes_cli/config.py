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

# TODO-自研: 从mimiraether_constants导入，保持与Hermes的兼容性
try:
    from mimiraether_constants import get_mimiraether_home
    # Hermes兼容层
    def get_hermes_home() -> Path:
        """Hermes兼容: 返回MimirAether配置目录"""
        return get_mimiraether_home()
except ImportError:
    # 回退到默认路径
    def get_hermes_home() -> Path:
        return Path.home() / ".openclaw"

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

# Hermes兼容: 暴露DEFAULT_CONFIG
DEFAULT_CONFIG = _get_default_config()

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


# =============================================================================
# Hermes兼容层 - TODO-自研: 需要完善这些函数的MimirAether实现
# =============================================================================

def get_project_root() -> Path:
    """Get the project installation directory (Hermes兼容)."""
    return Path(__file__).parent.parent.resolve()

def save_config(config: Dict[str, Any]):
    """Save configuration to ~/.openclaw/config.yaml (Hermes兼容层)."""
    ensure_config_home()
    config_path = get_config_path()
    config_path.parent.mkdir(parents=True, exist_ok=True)
    with open(config_path, 'w', encoding='utf-8') as f:
        yaml.dump(config, f, default_flow_style=False, allow_unicode=True)

def ensure_config_home():
    """Ensure config directory exists."""
    get_config_home().mkdir(parents=True, exist_ok=True)

# Hermes兼容别名
ensure_hermes_home = ensure_config_home


# =============================================================================
# .env 文件管理 (Hermes兼容)
# =============================================================================

import re
import stat
import tempfile

_ENV_VAR_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

# MimirAether不管理其他provider的env vars，这个列表保持为空
_EXTRA_ENV_KEYS = frozenset()

# MimirAether的默认配置版本
_CONFIG_VERSION = 1


def get_env_path() -> Path:
    """Get the .env file path (for API keys)."""
    return get_config_home() / ".env"


def get_env_value(key: str) -> Optional[str]:
    """Get a value from ~/.openclaw/.env or environment."""
    # Check environment first
    if key in os.environ:
        return os.environ[key]
    # Then check .env file
    env_vars = load_env()
    return env_vars.get(key)


def _sanitize_env_lines(lines: list) -> list:
    """Fix corrupted .env lines before reading or writing.

    Handles concatenated KEY=VALUE pairs on a single line.
    """
    sanitized: list[str] = []
    for line in lines:
        raw = line.rstrip("\r\n")
        stripped = raw.strip()

        # Preserve blank lines and comments
        if not stripped or stripped.startswith("#"):
            sanitized.append(raw + "\n")
            continue

        sanitized.append(stripped + "\n")

    return sanitized


def sanitize_env_file() -> int:
    """Read, sanitize, and rewrite ~/.openclaw/.env in place.

    Returns the number of lines that were fixed. Returns 0 when no changes needed.
    """
    env_path = get_env_path()
    if not env_path.exists():
        return 0

    with open(env_path, encoding="utf-8", errors="replace") as f:
        original_lines = f.readlines()

    sanitized = _sanitize_env_lines(original_lines)

    if sanitized == original_lines:
        return 0

    fixes = sum(1 for a, b in zip(original_lines, sanitized) if a != b)
    fixes += abs(len(sanitized) - len(original_lines))

    fd, tmp_path = tempfile.mkstemp(dir=str(env_path.parent), suffix=".tmp", prefix=".env_")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.writelines(sanitized)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, env_path)
    except BaseException:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise

    # Set permissions to owner-only
    try:
        os.chmod(env_path, stat.S_IRUSR | stat.S_IWUSR)
    except OSError:
        pass

    return fixes


def load_env() -> Dict[str, str]:
    """Load environment variables from ~/.openclaw/.env."""
    env_path = get_env_path()
    env_vars = {}

    if env_path.exists():
        with open(env_path, encoding="utf-8", errors="replace") as f:
            raw_lines = f.readlines()
        lines = _sanitize_env_lines(raw_lines)
        for line in lines:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, _, value = line.partition('=')
                env_vars[key.strip()] = value.strip().strip('"\'')

    return env_vars


def save_env_value(key: str, value: str):
    """Save or update a value in ~/.openclaw/.env."""
    if is_managed():
        managed_error(f"set {key}")
        return
    if not _ENV_VAR_NAME_RE.match(key):
        raise ValueError(f"Invalid environment variable name: {key!r}")
    value = value.replace("\n", "").replace("\r", "")
    ensure_config_home()
    env_path = get_env_path()

    lines = []
    if env_path.exists():
        with open(env_path, encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
        lines = _sanitize_env_lines(lines)

    # Find and update or append
    found = False
    for i, line in enumerate(lines):
        if line.strip().startswith(f"{key}="):
            lines[i] = f"{key}={value}\n"
            found = True
            break

    if not found:
        if lines and not lines[-1].endswith("\n"):
            lines[-1] += "\n"
        lines.append(f"{key}={value}\n")

    fd, tmp_path = tempfile.mkstemp(dir=str(env_path.parent), suffix='.tmp', prefix='.env_')
    try:
        with os.fdopen(fd, 'w', encoding="utf-8") as f:
            f.writelines(lines)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, env_path)
    except BaseException:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise

    # Set permissions to owner-only
    try:
        os.chmod(env_path, stat.S_IRUSR | stat.S_IWUSR)
    except OSError:
        pass

    os.environ[key] = value


def remove_env_value(key: str) -> bool:
    """Remove a key from ~/.openclaw/.env and os.environ.

    Returns True if the key was found and removed, False otherwise.
    """
    if is_managed():
        managed_error(f"remove {key}")
        return False
    if not _ENV_VAR_NAME_RE.match(key):
        raise ValueError(f"Invalid environment variable name: {key!r}")
    env_path = get_env_path()
    if not env_path.exists():
        os.environ.pop(key, None)
        return False

    with open(env_path, encoding="utf-8", errors="replace") as f:
        lines = f.readlines()
    lines = _sanitize_env_lines(lines)

    new_lines = [line for line in lines if not line.strip().startswith(f"{key}=")]
    found = len(new_lines) < len(lines)

    if found:
        fd, tmp_path = tempfile.mkstemp(dir=str(env_path.parent), suffix='.tmp', prefix='.env_')
        try:
            with os.fdopen(fd, 'w', encoding="utf-8") as f:
                f.writelines(new_lines)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_path, env_path)
        except BaseException:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise
        try:
            os.chmod(env_path, stat.S_IRUSR | stat.S_IWUSR)
        except OSError:
            pass

    os.environ.pop(key, None)
    return found


# =============================================================================
# Managed mode (Hermes兼容)
# =============================================================================

def get_managed_system() -> Optional[str]:
    """Return the package manager owning this install, if any."""
    raw = os.getenv("MIMIR_MANAGED", "").strip()
    if raw:
        normalized = raw.lower()
        if normalized in ("true", "1", "yes", "nixos", "homebrew", "brew"):
            return "NixOS" if normalized in ("nixos", "true", "1", "yes") else "Homebrew"

    managed_marker = get_config_home() / ".managed"
    if managed_marker.exists():
        return "NixOS"
    return None


def is_managed() -> bool:
    """Check if MimirAether is running in package-manager-managed mode."""
    return get_managed_system() is not None


def managed_error(action: str = "modify configuration"):
    """Print user-friendly error for managed mode."""
    managed_system = get_managed_system() or "a package manager"
    print(
        f"Cannot {action}: this MimirAether installation is managed by {managed_system}.\n"
        f"Use your package manager to upgrade or reinstall.",
        file=sys.stderr
    )


# =============================================================================
# Config migration helpers (Hermes兼容)
# =============================================================================

# Required env vars - MimirAether不需要强制要求的env vars
REQUIRED_ENV_VARS = {}

# Optional env vars for MimirAether
OPTIONAL_ENV_VARS = {
    "DEEPSEEK_API_KEY": {
        "description": "DeepSeek API key",
        "prompt": "DeepSeek API key",
        "url": "https://platform.deepseek.com/",
        "password": True,
        "category": "provider",
    },
    "OPENAI_API_KEY": {
        "description": "OpenAI API key",
        "prompt": "OpenAI API key",
        "url": "https://platform.openai.com/api-keys",
        "password": True,
        "category": "provider",
    },
    "TELEGRAM_BOT_TOKEN": {
        "description": "Telegram bot token",
        "prompt": "Telegram bot token",
        "url": "https://t.me/BotFather",
        "password": True,
        "category": "messaging",
    },
    "DISCORD_BOT_TOKEN": {
        "description": "Discord bot token",
        "prompt": "Discord bot token",
        "url": "https://discord.com/developers/applications",
        "password": True,
        "category": "messaging",
    },
}


def get_missing_env_vars(required_only: bool = False) -> list:
    """Check which environment variables are missing.

    Returns list of dicts with var info for missing variables.
    """
    missing = []

    for var_name, info in REQUIRED_ENV_VARS.items():
        if not get_env_value(var_name):
            missing.append({"name": var_name, **info, "is_required": True})

    if not required_only:
        for var_name, info in OPTIONAL_ENV_VARS.items():
            if not get_env_value(var_name):
                missing.append({"name": var_name, **info, "is_required": False})

    return missing


def _set_nested(config: dict, dotted_key: str, value):
    """Set a value at an arbitrarily nested dotted key path."""
    parts = dotted_key.split(".")
    current = config
    for part in parts[:-1]:
        if part not in current or not isinstance(current.get(part), dict):
            current[part] = {}
        current = current[part]
    current[parts[-1]] = value


def get_missing_config_fields() -> list:
    """Check which config fields are missing or outdated (recursive).

    Walks the DEFAULT_CONFIG tree and reports any keys present in defaults
    but absent from the user's loaded config.
    """
    config = load_config()
    missing = []

    default = _get_default_config()

    def _check(defaults: dict, current: dict, prefix: str = ""):
        for key, default_value in defaults.items():
            if key.startswith('_'):
                continue
            full_key = key if not prefix else f"{prefix}.{key}"
            if key not in current:
                missing.append({
                    "key": full_key,
                    "default": default_value,
                    "description": f"New config option: {full_key}",
                })
            elif isinstance(default_value, dict) and isinstance(current.get(key), dict):
                _check(default_value, current[key], full_key)

    _check(default, config)
    return missing


def get_container_exec_info() -> Optional[dict]:
    """Read container mode metadata from HERMES_HOME/.container-mode.

    Returns a dict with keys: backend, container_name, exec_user, hermes_bin
    or None if container mode is not active, we're already inside the
    container, or HERMES_DEV=1 is set.

    The .container-mode file is written by the NixOS activation script when
    container.enable = true. It tells the host CLI to exec into the container
    instead of running locally.
    """
    import os
    from pathlib import Path
    
    if os.environ.get("HERMES_DEV") == "1":
        return None

    from hermes_constants import is_container
    if is_container():
        return None

    # TODO-自研: get_hermes_home -> get_mimir_home for MimirAether
    container_mode_file = get_hermes_home() / ".container-mode"

    try:
        info = {}
        with open(container_mode_file, "r") as f:
            for line in f:
                line = line.strip()
                if "=" in line and not line.startswith("#"):
                    key, _, value = line.partition("=")
                    info[key.strip()] = value.strip()
    except FileNotFoundError:
        return None
    # All other exceptions (PermissionError, malformed data, etc.) propagate

    backend = info.get("backend", "docker")
    container_name = info.get("container_name", "hermes-agent")
    exec_user = info.get("exec_user", "hermes")
    hermes_bin = info.get("hermes_bin", "/data/current-package/bin/hermes")

    return {
        "backend": backend,
        "container_name": container_name,
        "exec_user": exec_user,
        "hermes_bin": hermes_bin,
    }


def check_config_version() -> tuple:
    """
    Check config version.
    
    Returns (current_version, latest_version).
    """
    config = load_config()
    current = config.get("_config_version", 0)
    latest = DEFAULT_CONFIG.get("_config_version", 1)
    return current, latest


def redact_key(key: str) -> str:
    """Redact an API key for display."""
    if not key:
        return "(not set)"
    if len(key) < 12:
        return "***"
    return key[:4] + "..." + key[-4:]


def save_env_value_secure(key: str, value: str) -> dict:
    save_env_value(key, value)
    return {
        "success": True,
        "stored_as": key,
        "validated": False,
    }
