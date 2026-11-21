"""Shared constants for MimirAether Agent - 统一版本"""

import os
import sys
from pathlib import Path

# Default when no env override (runtime data root; separate from git clone)
_DEFAULT_MIMIR_HOME = Path.home() / ".mimiraether"


def get_mimir_home() -> Path:
    """Return the MimirAether home directory (reads env on each call).

    Own-home keys only — ``HERMES_HOME`` is **Hermes'** own home key, never
    Mimir's. Sharing it made Mimir resolve to ``~/.hermes`` inside a Hermes
    environment, which produced false reds (2026-10-07, cross-env false-red
    family):

    1. ``MIMIR_AETHER_HOME``
    2. ``MIMIRAETHER_HOME``
    3. Default runtime data layout ``~/.mimiraether`` (not the git checkout)

    A set ``HERMES_HOME`` is ignored **loudly** (one stderr line per process,
    see :func:`_warn_ignored_hermes_home`) — never used as a home source.
    """
    for key in ("MIMIR_AETHER_HOME", "MIMIRAETHER_HOME"):
        v = os.getenv(key, "").strip()
        if v:
            return Path(v).expanduser()
    _warn_ignored_hermes_home()
    return _DEFAULT_MIMIR_HOME


_HERMES_HOME_WARNED = False


def _warn_ignored_hermes_home() -> None:
    """出声（每进程一次）：HERMES_HOME 是 Hermes 自家的键，已忽略。

    不出声的共用键 = 下一个读口又会静默指错家（第 20 单：三处假红全因静默共用键）。
    故必须可见，且**只警告不改行为**。
    """
    global _HERMES_HOME_WARNED
    if _HERMES_HOME_WARNED:
        return
    _HERMES_HOME_WARNED = True
    legacy = os.getenv("HERMES_HOME", "").strip()
    if not legacy:
        return
    try:
        legacy_path = Path(legacy).expanduser()
    except Exception:
        return
    if legacy_path == _DEFAULT_MIMIR_HOME:
        return  # 指向自家 —— 无歧义，不吵
    print(
        "[mimir-home] 忽略 HERMES_HOME=%s（Hermes 自家键）；Mimir 自家=%s。"
        "要覆盖请设 MIMIR_AETHER_HOME。" % (legacy_path, _DEFAULT_MIMIR_HOME),
        file=sys.stderr,
    )


# Snapshot at import — prefer calling :func:`get_mimir_home` when env may change.
MIMIR_HOME = get_mimir_home()


def get_mimir_data_dir() -> Path:
    """Persistent data under the project tree (sessions, caches, etc.)."""
    return get_mimir_home() / "data"


def get_cron_jobs_lock_path() -> Path:
    """Sidecar flock file shared by ALL writers of cron ``jobs.json`` (T91/B3-R1).

    Single source of truth so ``cron/jobs.py`` and ``scheduler/jobs.py`` — two
    independent storage implementations over the SAME runtime file — cannot
    drift onto different locks.  The lock is a **sidecar file**, never the
    target: flock-on-target is incompatible with tmp→replace atomic write
    (the fd dies at rename; ADR-001 方案 C / agent/persistent_store.py).  It
    lives under ``data/`` ⇒ same filesystem as jobs.json ⇒ flock semantics
    reliable, and is never renamed or deleted (flock releases on fd close,
    so there is no stale-lock state to clean up after a crash).
    """
    return get_mimir_data_dir() / "cron_jobs.write.lock"


def get_mimir_session_search_db_path() -> Path:
    """Session search SQLite path (IND-03 / ADR-003).

    Precedence: MIMIR_SESSION_DB > OPENCLAW_SESSION_DB (legacy) > data/sessions_search.db
    """
    override = os.getenv("MIMIR_SESSION_DB", "").strip()
    if override:
        return Path(override).expanduser()
    legacy = os.getenv("OPENCLAW_SESSION_DB", "").strip()  # legacy: ADR-003
    if legacy:
        return Path(legacy).expanduser()
    return get_mimir_data_dir() / "sessions_search.db"


def get_mimir_chroma_dir() -> Path:
    """Chroma persist root (ADR-006 / SEM-02).

    Precedence: MIMIR_CHROMA_DIR > {get_mimir_data_dir()}/chroma_sessions/
    """
    override = os.getenv("MIMIR_CHROMA_DIR", "").strip()
    if override:
        return Path(override).expanduser()
    return get_mimir_data_dir() / "chroma_sessions"


def get_mimir_sessions_dir() -> Path:
    """Gateway file-based session artifacts (distinct from SQLite ``state.db``)."""
    return get_mimir_data_dir() / "sessions"

# Backward compatibility aliases
def get_hermes_home() -> Path:
    """Alias for backward compatibility (dynamic — same as :func:`get_mimir_home`)."""
    return get_mimir_home()

HERMES_HOME = MIMIR_HOME
MIMIRAETHER_HOME = MIMIR_HOME

def get_mimir_dir(new_subpath: str, old_name: str) -> Path:
    """Resolve a MimirAether subdirectory."""
    home = get_mimir_home()
    old_path = home / old_name
    if old_path.exists():
        return old_path
    return home / new_subpath

def display_mimir_home() -> str:
    """Return user-friendly display string."""
    return str(get_mimir_home()).replace(str(Path.home()), "~")

display_hermes_home = display_mimir_home  # backward compat

def get_optional_skills_dir(default: Path | None = None) -> Path:
    """Return the optional-skills directory."""
    override = os.getenv("MIMIR_AETHER_OPTIONAL_SKILLS", "").strip()
    if override:
        return Path(override)
    if default is not None:
        return default
    return get_mimir_home() / "optional-skills"

get_optional_skills_dir_hermes = get_optional_skills_dir  # backward compat

# Additional backward compatibility
def get_hermes_dir(new_subpath: str, old_name: str) -> Path:
    """Alias for backward compatibility."""
    return get_mimir_dir(new_subpath, old_name)

# ── Hermes backward-compatible constants ──────────────────────────────────

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
OPENROUTER_MODELS_URL = f"{OPENROUTER_BASE_URL}/models"
AI_GATEWAY_BASE_URL = "https://ai-gateway.vercel.sh/v1"


# ── Hermes backward-compatible functions ──────────────────────────────────

def get_default_hermes_root() -> Path:
    """Return the root MimirAether directory for profile-level operations.

    In standard deployments this is ``~/.mimiraether`` (default home).

    In Docker or custom deployments where ``MIMIR_AETHER_HOME`` / ``HERMES_HOME``
    points outside ``~/.mimiraether`` (e.g. ``/opt/data``), returns that path
    directly — that IS the root.

    In profile mode where the home is ``<root>/profiles/<name>``,
    returns ``<root>`` so that ``profile list`` can see all profiles.
    Works both for standard (``~/.mimiraether/profiles/coder``) and Docker
    (``/opt/data/profiles/coder``) layouts.

    Import-safe — no dependencies beyond stdlib.
    """
    native_home = _DEFAULT_MIMIR_HOME
    env_home = os.environ.get("HERMES_HOME", "")
    if not env_home:
        env_home = os.environ.get("MIMIR_AETHER_HOME", "")
    if not env_home:
        return native_home
    env_path = Path(env_home).expanduser()
    try:
        env_path.resolve().relative_to(native_home.resolve())
        # Home is under default mimiraether root (normal or profile mode)
        return native_home
    except ValueError:
        pass

    # Docker / custom deployment.
    # Check if this is a profile path: <root>/profiles/<name>
    # If the immediate parent dir is named "profiles", the root is
    # the grandparent — this covers Docker profiles correctly.
    if env_path.parent.name == "profiles":
        return env_path.parent.parent

    # Not a profile path — HERMES_HOME itself is the root
    return env_path


def apply_ipv4_preference(force: bool = False) -> None:
    """Monkey-patch ``socket.getaddrinfo`` to prefer IPv4 connections.

    On servers with broken or unreachable IPv6, Python tries AAAA records
    first and hangs for the full TCP timeout before falling back to IPv4.
    This affects httpx, requests, urllib, the OpenAI SDK — everything that
    uses ``socket.getaddrinfo``.

    When *force* is True, patches ``getaddrinfo`` so that calls with
    ``family=AF_UNSPEC`` (the default) resolve as ``AF_INET`` instead,
    skipping IPv6 entirely.  If no A record exists, falls back to the
    original unfiltered resolution so pure-IPv6 hosts still work.

    Safe to call multiple times — only patches once.
    Set ``network.force_ipv4: true`` in ``config.yaml`` to enable.
    """
    if not force:
        return

    import socket

    # Guard against double-patching
    if getattr(socket.getaddrinfo, "_hermes_ipv4_patched", False):
        return

    _original_getaddrinfo = socket.getaddrinfo

    def _ipv4_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
        if family == 0:  # AF_UNSPEC — caller didn't request a specific family
            try:
                return _original_getaddrinfo(
                    host, port, socket.AF_INET, type, proto, flags
                )
            except socket.gaierror:
                # No A record — fall back to full resolution (pure-IPv6 hosts)
                return _original_getaddrinfo(host, port, family, type, proto, flags)
        return _original_getaddrinfo(host, port, family, type, proto, flags)

    _ipv4_getaddrinfo._hermes_ipv4_patched = True  # type: ignore[attr-defined]
    socket.getaddrinfo = _ipv4_getaddrinfo  # type: ignore[assignment]


# ── Environment detection functions ─────────────────────────────────────────

def is_termux() -> bool:
    """Return True when running inside a Termux (Android) environment.

    Checks ``TERMUX_VERSION`` (set by Termux) or the Termux-specific
    ``PREFIX`` path.  Import-safe — no heavy deps.
    """
    prefix = os.getenv("PREFIX", "")
    return bool(os.getenv("TERMUX_VERSION") or "com.termux/files/usr" in prefix)


_wsl_detected: bool | None = None


def is_wsl() -> bool:
    """Return True when running inside WSL (Windows Subsystem for Linux).

    Checks ``/proc/version`` for the ``microsoft`` marker that both WSL1
    and WSL2 inject.  Result is cached for the process lifetime.
    Import-safe — no heavy deps.
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


_container_detected: bool | None = None


def is_container() -> bool:
    """Return True when running inside a Docker/Podman container.

    Checks ``/.dockerenv`` (Docker), ``/run/.containerenv`` (Podman),
    and ``/proc/1/cgroup`` for container runtime markers.  Result is
    cached for the process lifetime.  Import-safe — no heavy deps.
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


# ── Path helper functions ─────────────────────────────────────────────────────

def get_subprocess_home() -> str | None:
    """Return a per-profile HOME directory for subprocesses, or None.

    When ``{HERMES_HOME}/home/`` exists on disk, subprocesses should use it
    as ``HOME`` so system tools (git, ssh, gh, npm …) write their configs
    inside the Hermes data directory instead of the OS-level ``/root`` or
    ``~/``.
    """
    hermes_home = os.getenv("HERMES_HOME")
    if not hermes_home:
        return None
    profile_home = os.path.join(hermes_home, "home")
    if os.path.isdir(profile_home):
        return profile_home
    return None


def get_config_path() -> Path:
    """Return the path to ``config.yaml`` under MIMIR_HOME."""
    return get_hermes_home() / "config.yaml"


# ── 配置单源读口（T95 · B1-F13 案 b′ · M3 收敛 · 2026-11-21）──────────────
#
# 背景：仓根 `config.yaml` 曾是 `delegation` / `smart_model_routing` 的**唯一**
# 真源——`tools/delegate_tool.py` 与 `agent/config_mixin.py` 按 ``__file__``
# 相对路径读它；其余读者读运行时件 ``$MIMIR_AETHER_HOME/config.yaml``
# ⇒ 同一个键两处真源（A4 双读者分歧）。
#
# 收敛后：**唯一读口 = :func:`get_config_path`**；仓根件降级为「迁移窗口兜底」，
# 且必须出声（缺段回落 = 静默降级，B1-F5 同族）。
# 验收判据：改运行时件 ⇒ 读数变；改仓根件 ⇒ 读数不变
# （见 ``tests/test_config_single_source.py``，两向）。

_REPO_CONFIG_ROOT = Path(__file__).resolve().parent
_LEGACY_CONFIG_WARNED = set()


def get_legacy_repo_config_paths() -> list:
    """仓根 ``config.yaml`` 候选（M3 之前的读点顺序）——**仅**迁移窗口兜底。"""
    return [
        _REPO_CONFIG_ROOT / "config.yaml",
        _REPO_CONFIG_ROOT / "mimicore" / "config" / "config.yaml",
        _REPO_CONFIG_ROOT / "mimicore" / "gateway" / "config.yaml",
    ]


def _read_yaml_doc(path: Path):
    try:
        if not path.exists():
            return None
        import yaml

        with open(path, encoding="utf-8") as f:
            doc = yaml.safe_load(f)
        return doc if isinstance(doc, dict) else None
    except Exception:
        return None


def _warn_legacy_config_read(caller: str, section: str, legacy: Path, primary: Path) -> None:
    """出声：运行时件缺该段、回落仓根件（每 caller+section 一次）。"""
    key = (caller, section)
    if key in _LEGACY_CONFIG_WARNED:
        return
    _LEGACY_CONFIG_WARNED.add(key)
    print(
        "[config-single-source] %s: 段 '%s' 在 %s 缺失 ⇒ 回落仓根件 %s"
        "（迁移窗口·请在运行时件补该段）" % (caller, section, primary, legacy),
        file=sys.stderr,
    )


def load_config_section(section: str, *, caller: str = "config"):
    """按**单源**顺序读一个配置段 → ``(段内容, 来源路径)``。

    顺序：① :func:`get_config_path`（运行时唯一真源）
         ② 仓根件候选（兜底·出声·仅迁移窗口）

    两处读者（``tools/delegate_tool`` / ``agent/config_mixin``）共用本函数
    ⇒ 不可能再出现「同一键两处真源」。
    """
    primary = get_config_path()
    doc = _read_yaml_doc(primary)
    if doc is not None:
        val = doc.get(section)
        if isinstance(val, dict) and val:
            return val, str(primary)
    for legacy in get_legacy_repo_config_paths():
        legacy_doc = _read_yaml_doc(legacy)
        if legacy_doc is None:
            continue
        legacy_val = legacy_doc.get(section)
        if isinstance(legacy_val, dict) and legacy_val:
            _warn_legacy_config_read(caller, section, legacy, primary)
            return legacy_val, str(legacy)
    if doc is not None and isinstance(doc.get(section), dict):
        return doc.get(section), str(primary)
    return {}, str(primary)


def get_skills_dir() -> Path:
    """Return the path to the skills directory under MIMIR_HOME."""
    return get_hermes_home() / "skills"


def get_env_path() -> Path:
    """Return the path to the ``.env`` file under MIMIR_HOME."""
    return get_hermes_home() / ".env"


VALID_REASONING_EFFORTS = ("minimal", "low", "medium", "high", "xhigh")


def parse_reasoning_effort(effort: str) -> dict | None:
    """Parse a reasoning effort level into a config dict.

    Valid levels: "none", "minimal", "low", "medium", "high", "xhigh".
    Returns None when the input is empty or unrecognized (caller uses default).
    Returns {"enabled": False} for "none".
    Returns {"enabled": True, "effort": <level>} for valid effort levels.
    """
    if not effort or not effort.strip():
        return None
    effort = effort.strip().lower()
    if effort == "none":
        return {"enabled": False}
    if effort in VALID_REASONING_EFFORTS:
        return {"enabled": True, "effort": effort}
    return None
