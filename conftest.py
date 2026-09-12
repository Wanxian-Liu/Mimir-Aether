"""Repo-root pytest isolation (2026-09-12 F1' — 让隔离覆盖全部测试树).

背景（2026-09-12 角色审计实证）: 只有 ``tests/`` 目录有 conftest，``agent/`` ·
``gateway/`` · ``tools/`` 树没有任何隔离 —— 裸 python3 跑 Gate2 时，测试进程直接写
生产 ``~/.mimiraether``：

- ``data/sessions_search.db`` 沉积夹具消息 800 行（sid-1 797 / sid 1 / sid-rw 2）
- ``data/chroma_sessions`` 沉积夹具向量 703 条
- ``logs/errors.log`` 每批次 14 行 ERROR（embedding resolve FAILED）→
  ``agent_error_rate`` 被推到 0.2 → ``/health`` 报 degraded

修复思路（最小改动）: 把隔离提升到 repo 根 conftest，在 ``pytest_configure``
（任何测试模块 import 之前）把运行时数据根与日志根重定向到会话级 tmp 目录，并摘掉已挂在
root logger 上的生产文件 handler。``tests/conftest.py`` 的 per-test 隔离保持原样（粒度更细，
二者兼容，都指向 tmp）。

契约（不得违反）:
- 生产根 ``~/.mimiraether`` 在测试会话期间只读。
- 只改落点、不改语义：不动 ``MIMIR_SESSION_SEARCH_INDEX`` /
  ``MIMIR_CHROMA_INCREMENTAL`` 等行为开关，避免让「默认开启」类断言失真。
- 逃生舱: ``MIMIR_PYTEST_KEEP_HOME=1`` 时不重定向（排查需要真实根时使用）。
"""

from __future__ import annotations

import logging
import os
import tempfile
from pathlib import Path

_PROD_HOME = Path.home() / ".mimiraether"

#: 三个等价 home 变量——三者都指向同一目录（见 mimir_constants.get_mimir_home）
_HOME_ENV_VARS = ("MIMIR_AETHER_HOME", "MIMIRAETHER_HOME", "HERMES_HOME")


def _detach_file_handlers_under(log_dir: Path) -> list:
    """摘掉写入 *log_dir* 的 root logger 文件 handler，返回被摘下的列表。

    兼容 ``RotatingFileHandler`` 子类（``mimiraether_logging._ManagedRotatingFileHandler``）
    与普通 ``FileHandler``——判据是 ``baseFilename`` 的父目录，而非 handler 类型。
    """
    log_dir = log_dir.resolve()
    root = logging.getLogger()
    removed = []
    for handler in list(root.handlers):
        base = getattr(handler, "baseFilename", None)
        if not base:
            continue
        try:
            is_prod = Path(base).resolve().parent == log_dir
        except (OSError, ValueError):
            continue
        if is_prod:
            root.removeHandler(handler)
            removed.append(handler)
    return removed


def _isolate_runtime_home() -> Path:
    home = Path(tempfile.mkdtemp(prefix="mimir-pytest-home-"))
    (home / "data").mkdir(parents=True, exist_ok=True)
    (home / "logs").mkdir(parents=True, exist_ok=True)
    for var in _HOME_ENV_VARS:
        os.environ[var] = str(home)
    # 幂等：即使某个测试模块在 import 期就把生产 handler 挂上了，也在这里摘掉
    _detach_file_handlers_under(_PROD_HOME / "logs")
    return home


def pytest_configure(config) -> None:
    """在任何测试模块被 import 之前重定向 home（含日志根）。"""
    if os.environ.get("MIMIR_PYTEST_KEEP_HOME"):
        return
    home = _isolate_runtime_home()
    config._mimir_pytest_home = home  # type: ignore[attr-defined]


def pytest_sessionstart(session) -> None:
    """再兜一次：插件/entry-point 可能在 configure 之后才挂生产 handler。"""
    if os.environ.get("MIMIR_PYTEST_KEEP_HOME"):
        return
    _detach_file_handlers_under(_PROD_HOME / "logs")
