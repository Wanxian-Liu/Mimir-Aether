#!/usr/bin/env python3
"""Skills Hub —— **hub 状态层**（目录 / 锁文件）· MimirAether 本地化移植。

上游真源：hermes agent 的 ``tools/skills_hub.py``（其 docstring 自述是 library module，
拥有 hub 路径 / guarded HTTP / 索引缓存 / 锁文件 / taps / 审计日志；install-uninstall 在
``tools.skills_hub_install``，索引-路由-搜索在 ``tools.skills_hub_search``）。

**本文件只移植状态层**：路径解析 / ``_JsonStateFile`` / ``HubLockFile`` / ``ensure_hub_dirs``
—— 供 ``mimir_cli/skills_hub.py::do_list()`` 判定「hub 安装来源」。
磁盘布局与上游一致（``<skills_dir>/.hub/lock.json``，``{"version":1,"installed":{}}``），
仅把 home 换成 ``mimir_constants.get_skills_dir()`` 体系。

**未移植（跟踪项）**：``GitHubAuth`` / ``create_source_router`` / ``quarantine_bundle`` /
``install_from_quarantine`` / ``TapsManager`` / ``append_audit_log`` 及 guarded HTTP 与
sibling 模块 —— 于是 ``do_install`` 等路径仍不可用，且**本仓无写入者**生成 lock.json。
访问未移植名字一律**显式抛错**（``__getattr__``），不兜底、不吞错、不返回假值。
"""

import json
import logging
import os
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_HUB_DIRNAME = ".hub"

# 未移植名字 -> 上游所属模块（用于报错指路；不懒加载、不兜底）
_UNPORTED = {
    "GitHubAuth": "tools.skills_hub_auth",
    "create_source_router": "tools.skills_hub_search",
    "unified_search": "tools.skills_hub_search",
    "quarantine_bundle": "tools.skills_hub_install",
    "install_from_quarantine": "tools.skills_hub_install",
    "uninstall_skill": "tools.skills_hub_install",
    "TapsManager": "tools.skills_hub",
    "append_audit_log": "tools.skills_hub",
    "source_url_for_bundle": "tools.skills_hub_models",
}


def _skills_dir() -> Path:
    """hub 状态文件的宿主技能目录（与运行时 ``get_skills_dir()`` 一致）。"""
    from mimir_constants import get_skills_dir

    return Path(get_skills_dir())


def hub_dir() -> Path:
    """``<skills_dir>/.hub``"""
    return _skills_dir() / _HUB_DIRNAME


def _lock_file() -> Path:
    """``<skills_dir>/.hub/lock.json``"""
    return hub_dir() / "lock.json"


def _index_cache_dir() -> Path:
    """``<skills_dir>/.hub/index-cache``"""
    return hub_dir() / "index-cache"


def ensure_hub_dirs() -> None:
    """幂等创建 hub 状态目录（只建目录，不建文件；与上游同名函数同义）。"""
    for p in (hub_dir(), _index_cache_dir()):
        try:
            p.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            logger.warning("Could not create hub dir %s: %s", p, e)


class _JsonStateFile:
    """hub 目录下的 JSON 状态文件；缺失/损坏时返回 ``EMPTY`` 的深拷贝。"""

    EMPTY: dict = {}
    DEFAULT_PATH: Any = None

    def __init__(self, path=None):
        self.path = path if path is not None else type(self).DEFAULT_PATH()

    def _read(self) -> dict:
        try:
            return json.loads(self.path.read_text(encoding="utf-8-sig"))
        except (json.JSONDecodeError, OSError):
            return deepcopy(self.EMPTY)

    def _write(self, data: dict, ensure_ascii: bool = False) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_name(self.path.name + ".tmp")
            tmp.write_text(
                json.dumps(data, ensure_ascii=ensure_ascii, default=str, indent=2),
                encoding="utf-8",
            )
            os.replace(tmp, self.path)
        except OSError as e:
            logger.warning("Could not write hub state %s: %s", self.path, e)


class HubLockFile(_JsonStateFile):
    """``<skills_dir>/.hub/lock.json`` —— 已安装 hub 技能的来源登记。"""

    EMPTY = {"version": 1, "installed": {}}
    DEFAULT_PATH = staticmethod(_lock_file)

    def load(self) -> dict:
        data = self._read()
        if not isinstance(data, dict) or not isinstance(data.get("installed"), dict):
            logger.warning("HubLockFile malformed at %s -- treating as empty", self.path)
            return deepcopy(self.EMPTY)
        return data

    def save(self, data: dict) -> None:
        self._write(data, ensure_ascii=False)

    def get_installed(self, name: str) -> Optional[dict]:
        return self.load()["installed"].get(name)

    def list_installed(self) -> List[dict]:
        return [{"name": n, **e} for n, e in self.load()["installed"].items()]


def __getattr__(name: str):
    """未移植名字：显式抛错并指路，**不做假实现、不吞错**。"""
    if name in _UNPORTED:
        raise AttributeError(
            "tools.skills_hub." + name + " 未移植（上游定义于 " + _UNPORTED[name] + "）。"
            "本模块目前只含 hub 状态层（HubLockFile / ensure_hub_dirs）；"
            "完整 hub 子系统移植见 Q8 回执「未覆盖面」。"
        )
    raise AttributeError("module " + repr(__name__) + " has no attribute " + repr(name))
