"""
MimirAether Constants Module

学习自Hermes hermes_constants.py设计思路：
- 统一的路径管理
- 环境检测(WSL, Termux, Container)
- 配置路径管理
- Skills目录管理

核心原则：
- 无循环导入
- 仅依赖stdlib
- 跨模块共享常量
"""

import os
from pathlib import Path
from typing import Optional


# ============================================================================
# 路径管理
# ============================================================================

def get_mimir_home() -> Path:
    """
    返回MimirAether主目录（默认：~/.mimir）
    
    读取 MIMIR_HOME 环境变量，回退到 ~/.mimir
    这是单一数据源 - 所有其他模块应导入此函数
    """
    return Path(os.getenv("MIMIR_HOME", Path.home() / ".mimir"))


def get_mimir_root() -> Path:
    """
    返回MimirAether根目录，用于profile级别的操作
    
    标准部署：~/.mimir
    Docker部署：MIMIR_HOME指向的目录
    Profile模式：<root>/profiles/<name>
    """
    native_home = Path.home() / ".mimir"
    env_home = os.environ.get("MIMIR_HOME", "")
    if not env_home:
        return native_home
    
    env_path = Path(env_home)
    try:
        env_path.resolve().relative_to(native_home.resolve())
        return native_home
    except ValueError:
        pass
    
    # Docker / 自定义部署
    if env_path.parent.name == "profiles":
        return env_path.parent.parent
    
    return env_path


def get_skills_dir() -> Path:
    """返回skills目录路径（位于MIMIR_HOME下）"""
    return get_mimir_home() / "skills"


def get_optional_skills_dir(default: Optional[Path] = None) -> Path:
    """
    返回可选skills目录，支持包管理器包装
    
    打包安装可能将optional-skills放在Python包树外，
    通过MIMIR_OPTIONAL_SKILLS环境变量暴露
    """
    override = os.getenv("MIMIR_OPTIONAL_SKILLS", "").strip()
    if override:
        return Path(override)
    if default is not None:
        return default
    return get_mimir_home() / "optional-skills"


def get_mimir_dir(new_subpath: str, old_name: str) -> Path:
    """
    解析MimirAether子目录，提供向后兼容
    
    新安装使用统一布局（如cache/images）
    已安装且有旧路径的保留原路径
    """
    home = get_mimir_home()
    old_path = home / old_name
    if old_path.exists():
        return old_path
    return home / new_subpath


def get_config_path() -> Path:
    """返回config.yaml路径"""
    return get_mimir_home() / "config.yaml"


def get_env_path() -> Path:
    """返回.env文件路径"""
    return get_mimir_home() / ".env"


def get_sessions_dir() -> Path:
    """返回sessions目录路径"""
    return get_mimir_home() / "sessions"


def get_memory_dir() -> Path:
    """返回memory目录路径"""
    return get_mimir_home() / "memory"


def get_skills_snapshot_path() -> Path:
    """返回skills prompt snapshot文件路径"""
    return get_mimir_home() / ".skills_prompt_snapshot.json"


def display_mimir_home() -> str:
    """
    返回用户友好的MIMIR_HOME显示字符串
    
    使用~/简写增强可读性
    """
    home = get_mimir_home()
    try:
        return "~/" + str(home.relative_to(Path.home()))
    except ValueError:
        return str(home)


def get_subprocess_home() -> Optional[str]:
    """
    返回subprocess使用的HOME目录
    
    当{MIMIR_HOME}/home/存在时，subprocess使用它
    这样系统工具(git, ssh, gh等)的配置写入MimirAether数据目录
    """
    mimir_home = os.getenv("MIMIR_HOME")
    if not mimir_home:
        return None
    profile_home = os.path.join(mimir_home, "home")
    if os.path.isdir(profile_home):
        return profile_home
    return None


# ============================================================================
# 环境检测
# ============================================================================

_wsl_detected: Optional[bool] = None


def is_wsl() -> bool:
    """
    检测是否运行在WSL中
    
    检查/proc/version中的microsoft标记，
    WSL1和WSL2都会注入此标记
    """
    global _wsl_detected
    if _wsl_detected is not None:
        return _wsl_detected
    try:
        with open("/proc/version", "r") as f:
            _wsl_detected = "microsoft" in f.read().lower()
    except Exception:
        _wsl_detected = False
    return _wsl_detected


_container_detected: Optional[bool] = None


def is_container() -> bool:
    """
    检测是否运行在Docker/Podman容器中
    
    检查 /.dockerenv (Docker), /run/.containerenv (Podman),
    和 /proc/1/cgroup中的容器运行时标记
    """
    global _container_detected
    if _container_detected is not None:
        return _container_detected
    if os.path.exists("/.dockerenv"):
        _container_detected = True
        return True
    if os.path.exists("/run/.containerenv"):
        _container_detected = True
        return True
    try:
        with open("/proc/1/cgroup", "r") as f:
            cgroup = f.read()
            if "docker" in cgroup or "podman" in cgroup or "/lxc/" in cgroup:
                _container_detected = True
                return True
    except OSError:
        pass
    _container_detected = False
    return False


_termux_detected: Optional[bool] = None


def is_termux() -> bool:
    """
    检测是否运行在Termux(Android)中
    
    检查TERMUX_VERSION或Termux特定的PREFIX路径
    """
    global _termux_detected
    if _termux_detected is not None:
        return _termux_detected
    prefix = os.getenv("PREFIX", "")
    _termux_detected = bool(os.getenv("TERMUX_VERSION") or "com.termux/files/usr" in prefix)
    return _termux_detected


# ============================================================================
# 网络偏好
# ============================================================================

def apply_ipv4_preference(force: bool = False) -> None:
    """
    修补socket.getaddrinfo优先使用IPv4
    
    在IPv6损坏或不可达的服务上，
    Python先尝试AAAA记录然后超时才回退到IPv4
    """
    if not force:
        return
    
    import socket
    
    if getattr(socket.getaddrinfo, "_mimir_ipv4_patched", False):
        return
    
    _original_getaddrinfo = socket.getaddrinfo
    
    def _ipv4_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
        if family == 0:
            try:
                return _original_getaddrinfo(host, port, socket.AF_INET, type, proto, flags)
            except socket.gaierror:
                return _original_getaddrinfo(host, port, family, type, proto, flags)
        return _original_getaddrinfo(host, port, family, type, proto, flags)
    
    _ipv4_getaddrinfo._mimir_ipv4_patched = True  # type: ignore[attr-defined]
    socket.getaddrinfo = _ipv4_getaddrinfo  # type: ignore[assignment]


# ============================================================================
# Well-Known URLs
# ============================================================================

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
OPENROUTER_MODELS_URL = f"{OPENROUTER_BASE_URL}/models"

# ============================================================================
# 工具函数
# ============================================================================

def ensure_mimir_dirs() -> None:
    """确保MimirAether所需的目录存在"""
    home = get_mimir_home()
    dirs = [
        home,
        get_sessions_dir(),
        get_memory_dir(),
        get_skills_dir(),
    ]
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)


# ============================================================================
# 初始化：确保目录存在
# ============================================================================

# 延迟初始化，避免导入时创建目录
_init_done = False


def ensure_initialized():
    """确保MimirAether初始化完成"""
    global _init_done
    if not _init_done:
        ensure_mimir_dirs()
        _init_done = True
