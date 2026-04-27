"""MimirAether config module - stubs that delegate to hermes_constants and mimiraether modules.

This module provides compatibility shims for hermes_cli imports.
All paths are aligned with ~/.openclaw/ (via hermes_constants).
"""

import os
import re
import yaml
from pathlib import Path
from typing import Any, Optional

# Delegate path functions to hermes_constants
from hermes_constants import (
    get_hermes_home as _hermes_get_hermes_home,
    get_config_path as _hermes_get_config_path,
    get_env_path as _hermes_get_env_path,
)

# ─── Path functions ──────────────────────────────────────────────────────────

def get_hermes_home() -> Path:
    return _hermes_get_hermes_home()

def get_config_path() -> Path:
    return _hermes_get_config_path()

def get_env_path() -> Path:
    return _hermes_get_env_path()

def get_project_root() -> Path:
    """Return the MimirAether project root directory."""
    # Try to find the project root by looking for marker files
    cwd = Path.cwd()
    for path in [cwd, *cwd.parents]:
        if (path / "hermes_cli").is_dir() and (path / "gateway").is_dir():
            return path
    # Fallback: return parent of hermes_cli package
    return Path(__file__).parent.parent

# ─── Config loading ──────────────────────────────────────────────────────────

def load_config() -> dict[str, Any]:
    """Load the config.yaml file from HERMES_HOME."""
    config_path = get_config_path()
    if config_path.exists():
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        except (yaml.YAMLError, OSError):
            return {}
    return {}

def save_config(config: dict[str, Any]) -> None:
    """Save the config dict to config.yaml in HERMES_HOME."""
    config_path = get_config_path()
    config_path.parent.mkdir(parents=True, exist_ok=True)
    with open(config_path, "w", encoding="utf-8") as f:
        yaml.safe_dump(config, f, default_flow_style=False, allow_unicode=True)

def read_raw_config() -> str:
    """Read raw config.yaml content."""
    config_path = get_config_path()
    if config_path.exists():
        return config_path.read_text(encoding="utf-8")
    return ""

# ─── Default config ─────────────────────────────────────────────────────────

def _get_default_config() -> dict[str, Any]:
    """Return the default configuration dict."""
    return {
        "agent": {
            "restart_drain_timeout": 60,
        },
    }

DEFAULT_CONFIG = _get_default_config()

# ─── Environment helpers ─────────────────────────────────────────────────────

def _sanitize_env_lines(lines: list[str]) -> list[str]:
    """Remove sensitive values from .env lines for display."""
    result = []
    for line in lines:
        line = line.rstrip()
        if "=" in line and not line.strip().startswith("#"):
            key, *rest = line.split("=", 1)
            val = rest[0] if rest else ""
            if val and not val.startswith('"') and not val.startswith("'"):
                # Mask the value if it looks sensitive
                if any(kw in key.upper() for kw in ["KEY", "TOKEN", "SECRET", "PASSWORD", "AUTH"]):
                    val = "***"
            line = f"{key}={val}"
        result.append(line)
    return result

def load_env() -> dict[str, str]:
    """Load environment variables from .env file as a dict."""
    env_path = get_env_path()
    result = {}
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, val = line.split("=", 1)
                key = key.strip()
                val = val.strip().strip('"').strip("'")
                result[key] = val
    return result

def ensure_hermes_home() -> Path:
    """Ensure HERMES_HOME exists and return the path."""
    home = get_hermes_home()
    home.mkdir(parents=True, exist_ok=True)
    return home

def redact_key(value: Optional[str]) -> str:
    """Redact a sensitive value for display (show first 4 and last 4 chars)."""
    if not value:
        return ""
    if len(value) <= 8:
        return "****"
    return value[:4] + "****" + value[-4:]

def get_env_value(key: str) -> Optional[str]:
    """Get an environment variable value, checking .env file."""
    # First check actual env
    val = os.getenv(key)
    if val is not None:
        return val
    # Then check .env file
    env_path = get_env_path()
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("#") or not line:
                continue
            if "=" in line:
                k, v = line.split("=", 1)
                if k.strip() == key:
                    return v.strip().strip('"').strip("'")
    return None

def save_env_value(key: str, value: str) -> None:
    """Save an environment variable to the .env file."""
    env_path = get_env_path()
    env_path.parent.mkdir(parents=True, exist_ok=True)
    
    lines = []
    if env_path.exists():
        lines = env_path.read_text(encoding="utf-8").splitlines()
    
    # Find and replace or append
    new_lines = []
    found = False
    for line in lines:
        if line.strip().startswith("#"):
            new_lines.append(line)
            continue
        if "=" in line:
            k = line.split("=", 1)[0].strip()
            if k == key:
                new_lines.append(f'{key}="{value}"')
                found = True
                continue
        new_lines.append(line)
    
    if not found:
        new_lines.append(f'{key}="{value}"')
    
    env_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")

def save_env_value_secure(key: str, value: str) -> None:
    """Save an environment variable securely (same as save_env_value for now)."""
    save_env_value(key, value)

def remove_env_value(key: str) -> None:
    """Remove an environment variable from the .env file."""
    env_path = get_env_path()
    if not env_path.exists():
        return
    
    lines = env_path.read_text(encoding="utf-8").splitlines()
    new_lines = []
    for line in lines:
        if line.strip().startswith("#"):
            new_lines.append(line)
            continue
        if "=" in line:
            k = line.split("=", 1)[0].strip()
            if k == key:
                continue  # Remove this line
        new_lines.append(line)
    
    env_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")

# ─── Config migration/validation ────────────────────────────────────────────

def check_config_version(config: dict[str, Any]) -> bool:
    """Check if config has the expected version structure."""
    return isinstance(config, dict)

def migrate_config(config: dict[str, Any]) -> dict[str, Any]:
    """Migrate config to current version (no-op for now)."""
    return config

def validate_config_structure(config: dict[str, Any]) -> tuple[bool, Optional[str]]:
    """Validate config structure. Returns (valid, error_message)."""
    if not isinstance(config, dict):
        return False, "Config must be a dictionary"
    return True, None

# ─── Managed config ──────────────────────────────────────────────────────────

def is_managed() -> bool:
    """Return True if running in managed/package environment."""
    return False

def managed_error(message: str) -> None:
    """Raise an error for managed environment violations."""
    raise RuntimeError(message)

# ─── Optional environment variables (for web UI) ─────────────────────────────

OPTIONAL_ENV_VARS: dict[str, dict[str, Any]] = {
    "ANTHROPIC_API_KEY": {
        "description": "Anthropic API key for Claude models",
        "url": "https://console.anthropic.com/settings/keys",
        "category": "model",
        "password": True,
        "tools": ["anthropic"],
        "advanced": False,
    },
    "OPENAI_API_KEY": {
        "description": "OpenAI API key for GPT models",
        "url": "https://platform.openai.com/api-keys",
        "category": "model",
        "password": True,
        "tools": ["openai"],
        "advanced": False,
    },
    "NOUS_API_KEY": {
        "description": "Nous Research API key",
        "url": "https://console.nousresearch.com/",
        "category": "model",
        "password": True,
        "tools": ["nous"],
        "advanced": True,
    },
    "DASHSCOPE_API_KEY": {
        "description": "Alibaba DashScope API key for Qwen models",
        "url": "https://dashscope.console.aliyun.com/",
        "category": "model",
        "password": True,
        "tools": ["qwen"],
        "advanced": True,
    },
    "GOOGLE_API_KEY": {
        "description": "Google API key for Gemini models",
        "url": "https://aistudio.google.com/app/apikey",
        "category": "model",
        "password": True,
        "tools": ["google"],
        "advanced": True,
    },
    "DEEPSEEK_API_KEY": {
        "description": "DeepSeek API key",
        "url": "https://platform.deepseek.com/",
        "category": "model",
        "password": True,
        "tools": ["deepseek"],
        "advanced": True,
    },
    "OPENROUTER_API_KEY": {
        "description": "OpenRouter API key for accessing multiple models",
        "url": "https://openrouter.ai/keys",
        "category": "model",
        "password": True,
        "tools": ["openrouter"],
        "advanced": True,
    },
    "TOGETHER_API_KEY": {
        "description": "Together AI API key",
        "url": "https://api.together.xyz/",
        "category": "model",
        "password": True,
        "tools": ["together"],
        "advanced": True,
    },
    "AZURE_OPENAI_API_KEY": {
        "description": "Azure OpenAI API key",
        "url": "https://portal.azure.com/",
        "category": "model",
        "password": True,
        "tools": ["azure"],
        "advanced": True,
    },
    "TELEGRAM_BOT_TOKEN": {
        "description": "Telegram bot token for messaging",
        "url": "https://core.telegram.org/bots#creating-a-new-bot",
        "category": "channel",
        "password": True,
        "tools": ["telegram"],
        "advanced": False,
    },
    "DISCORD_BOT_TOKEN": {
        "description": "Discord bot token for messaging",
        "url": "https://discord.com/developers/applications",
        "category": "channel",
        "password": True,
        "tools": ["discord"],
        "advanced": True,
    },
    "FEISHU_APP_ID": {
        "description": "Feishu (Lark) app ID",
        "url": "https://open.feishu.cn/",
        "category": "channel",
        "password": False,
        "tools": ["feishu"],
        "advanced": True,
    },
    "FEISHU_APP_SECRET": {
        "description": "Feishu (Lark) app secret",
        "url": "https://open.feishu.cn/",
        "category": "channel",
        "password": True,
        "tools": ["feishu"],
        "advanced": True,
    },
}

# ─── Custom providers ────────────────────────────────────────────────────────

def get_compatible_custom_providers() -> list[dict[str, Any]]:
    """Return list of compatible custom provider configs."""
    return []

# ─── Update helpers ──────────────────────────────────────────────────────────

def recommended_update_command() -> str:
    """Return the recommended update command."""
    return "openclaw self-update"
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


